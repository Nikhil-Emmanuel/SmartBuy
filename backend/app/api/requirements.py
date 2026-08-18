"""Requirement generation and editing. API contract section 2."""

from __future__ import annotations

from fastapi import APIRouter

from app.agent import orchestrator
from app.api.deps import CurrentUser, DbSession
from app.api.serializers import requirements_response
from app.core.errors import RequirementNotFound, SessionNotFound, ValidationError
from app.models.plan import Requirement
from app.schemas.plan import (
    GenerateRequirementsRequest,
    RequirementPatch,
    RequirementsResponse,
)
from app.services import plan_service

router = APIRouter(prefix="/api/requirements", tags=["requirements"])


@router.post("/generate", response_model=RequirementsResponse)
def generate_requirements(payload: GenerateRequirementsRequest, db: DbSession,
                          user: CurrentUser) -> RequirementsResponse:
    """Build a plan from the session's slots.

    Usually the chat turn has already done this; this endpoint exists so the
    frontend can regenerate after the user edits slots in the sidebar.
    """
    session = orchestrator.get_session(db, payload.session_id)
    if session is None:
        raise SessionNotFound(f"No session with id {payload.session_id}.")

    slots = orchestrator.session_slots(session)
    if not slots.activity and not slots.goal_text:
        raise ValidationError("Tell me what you are shopping for first.")

    creation = plan_service.create_plan(
        db, slots=slots.to_context(), user=user, session_id=session.id
    )
    db.commit()
    return requirements_response(creation.plan)


@router.get("/{plan_id}", response_model=RequirementsResponse)
def get_requirements(plan_id: str, db: DbSession) -> RequirementsResponse:
    return requirements_response(plan_service.get_plan(db, plan_id))


@router.patch("/{requirement_id}", response_model=RequirementsResponse)
def patch_requirement(requirement_id: str, payload: RequirementPatch, db: DbSession,
                      user: CurrentUser) -> RequirementsResponse:
    """Tick "I already have this", or change a quantity.

    Both change the budget maths, so the plan is re-optimized immediately --
    the user is looking straight at the number that has to update.
    """
    requirement = db.get(Requirement, requirement_id)
    if requirement is None:
        raise RequirementNotFound(f"No requirement with id {requirement_id}.")

    plan = plan_service.get_plan(db, requirement.plan_id)

    if payload.quantity is not None:
        requirement.quantity = payload.quantity
    if payload.is_owned is not None:
        plan_service.set_requirement_owned(
            db, plan, requirement_id, payload.is_owned, user=user
        )
    elif payload.quantity is not None:
        plan_service.optimize_plan(db, plan, user=user)

    db.commit()
    return requirements_response(plan)
