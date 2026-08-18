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


def _session_or_404(db, session_id: str) -> ChatSession:
    session = orchestrator.get_session(db, session_id)
    if session is None:
        raise SessionNotFound(f"No session with id {session_id}.")
    return session


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: DbSession, user: CurrentUser) -> ChatResponse:
    if payload.session_id:
        session = orchestrator.get_session(db, payload.session_id)
        if session is None:
            # A client-minted id that we have not seen: adopt it rather than
            # 404-ing, so a page refresh never loses the conversation.
            session = orchestrator.create_session(db, user)
            session.id = payload.session_id
            db.flush()
    else:
        session = orchestrator.create_session(db, user)

    response = orchestrator.handle_message(db, session, payload.message, user)
    db.commit()
    return response


@router.get("/session/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DbSession) -> SessionResponse:
    session = _session_or_404(db, session_id)
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
    session = _session_or_404(db, session_id)
    orchestrator.apply_slot_update(db, session, payload.model_dump(), user)
    db.commit()
    return get_session(session_id, db)
