"""Chat and session endpoints. API contract section 1.

Wave 2, and the spine of the whole application. Everything here is a thin
wrapper over app.agent.orchestrator -- the router owns HTTP, the orchestrator
owns behaviour.

LLM_UNAVAILABLE is never returned from a chat turn: the deterministic path
handles it and the response carries `degraded: true` instead.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.agent import orchestrator
from app.api.deps import CurrentUser, DbSession
from app.core.errors import SessionNotFound
from app.models.session import ChatSession
from app.schemas.agent import (
    ChatRequest,
    ChatResponse,
    MessageOut,
    SessionResponse,
    SlotUpdateRequest,
)

router = APIRouter(prefix="/api", tags=["chat"])


def _session_or_404(db, session_id: str, user) -> ChatSession:
    """Fetch a conversation, refusing to hand it to anyone but its owner.

    There is no login (ADR-005), so `X-Session-Id` is the only claim of
    identity we have -- but it is a claim we were not checking. Conversations
    hold the user's goal, budget and location, and a conversation id is
    enough to read or continue one. UUID4 ids make that hard to exploit
    blindly, but "hard to guess" is not an access control.

    A mismatch is reported as 404 rather than 403: telling a stranger that the
    id they tried does exist, and merely belongs to someone else, is itself a
    disclosure. Sessions with no owner predate this check and stay readable.
    """
    session = orchestrator.get_session(db, session_id)
    if session is None:
        raise SessionNotFound(f"No session with id {session_id}.")
    if session.user_id and user is not None and session.user_id != user.id:
        raise SessionNotFound(f"No session with id {session_id}.")
    return session


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: DbSession, user: CurrentUser) -> ChatResponse:
    if payload.session_id:
        session = orchestrator.get_session(db, payload.session_id)
        if session is not None and session.user_id and session.user_id != user.id:
            # Posting someone else's conversation id must not append to their
            # conversation. Start a fresh one instead of failing the turn --
            # the caller gets a working chat, just not that one.
            session = None
        if session is None:
            # A client-minted id that we have not seen: adopt it rather than
            # 404-ing, so a page refresh never loses the conversation.
            session = orchestrator.create_session(db, user)
            if orchestrator.get_session(db, payload.session_id) is None:
                session.id = payload.session_id
            db.flush()
    else:
        session = orchestrator.create_session(db, user)

    response = orchestrator.handle_message(db, session, payload.message, user)
    db.commit()
    return response


@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DbSession, user: CurrentUser) -> SessionResponse:
    session = _session_or_404(db, session_id, user)
    plan = orchestrator.latest_plan(db, session.id)

    return SessionResponse(
        session_id=session.id,
        state=session.state,
        intent=session.intent,
        slots=orchestrator.session_slots(session),
        assumptions=session.assumptions or [],
        messages=[
            MessageOut(
                role=m.role,
                content=m.content,
                meta=m.meta or {},
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in session.messages
        ],
        plan_id=plan.id if plan else None,
    )


@router.post("/session/{session_id}/slots", response_model=SessionResponse)
def update_slots(session_id: str, payload: SlotUpdateRequest, db: DbSession,
                 user: CurrentUser) -> SessionResponse:
    """Manual slot correction from the sidebar.

    The plan is marked stale rather than rebuilt on the spot: regenerating is
    the user's call, and doing it silently would change what they are looking
    at mid-sentence.
    """
    session = _session_or_404(db, session_id, user)
    orchestrator.apply_slot_update(db, session, payload.model_dump(), user)
    db.commit()
    return get_session(session_id, db, user)
