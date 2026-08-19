"""Personalised offers, from the trained shopper-segment model.

One endpoint, and it is a read: the model proposes an offer and never writes
one. Persisting a discount is a commercial action and stays behind the normal
validated paths (ADR: the LLM and the model both propose, the application
decides).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, DbSession
from app.services import personalization

router = APIRouter(prefix="/api", tags=["personalization"])


class PersonalizationOut(BaseModel):
    segment: str | None = Field(None, description="Predicted shopper segment.")
    label: str | None = Field(None, description="How the segment is shown to the user.")
    confidence: float = Field(0.0, description="Model probability for the predicted class.")
    rationale: str | None = Field(
        None, description="Why this behaviour implies this offer, in plain words."
    )
    discount_pct: int = 0
    coupon_code: str | None = None
    perk: str | None = Field(
        None, description="Non-price benefit, where a discount is the wrong lever."
    )
    events_considered: int = Field(
        0, description="How many recorded interactions the prediction was based on."
    )
    status: str = Field(
        ...,
        description=(
            "ok | insufficient_history | low_confidence | model_unavailable. "
            "Anything other than 'ok' means no personalised offer was issued, "
            "and the reason is stated rather than hidden."
        ),
    )
    is_model_generated: bool = Field(
        True,
        description=(
            "Always true: this response comes from a trained classifier, not a "
            "hand-written rule. The offer policy attached to the predicted "
            "segment is hand-written and reviewable."
        ),
    )


@router.get("/personalization", response_model=PersonalizationOut)
def my_personalization(db: DbSession, user: CurrentUser) -> PersonalizationOut:
    """The current user's segment and the offer it earns them.

    Scoped to the caller's own session. There is no route to ask about somebody
    else's segment -- a shopper's inferred spending profile is exactly the kind
    of derived personal data that should not be readable by id.
    """
    result = personalization.personalize(db, user.id)
    return PersonalizationOut(**result.to_dict())
