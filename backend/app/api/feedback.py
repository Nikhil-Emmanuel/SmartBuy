"""Feedback and interaction signals. API contract section 6."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import product_out
from app.core.constants import FeedbackType, InteractionType
from app.core.errors import ProductNotFound, ValidationError
from app.models.feedback import Feedback
from app.models.product import Product, ProductInteraction
from app.schemas.feedback import (
    FeedbackRequest,
    FeedbackResponse,
    InteractionRequest,
    PreferencesOut,
)
from app.schemas.product import ProductOut
from app.services import preference_learning

router = APIRouter(prefix="/api", tags=["feedback"])

VALID_FEEDBACK = {f.value for f in FeedbackType}
VALID_INTERACTIONS = {i.value for i in InteractionType}


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(payload: FeedbackRequest, db: DbSession,
                    user: CurrentUser) -> FeedbackResponse:
    """Record a thumbs up/down and update preference tracking.

    We call this preference *tracking*, not learning: it is a decayed counter,
    and claiming otherwise would be a claim we cannot support.
    """
    if payload.feedback_type not in VALID_FEEDBACK:
        raise ValidationError(
            f"feedback_type must be one of {', '.join(sorted(VALID_FEEDBACK))}."
        )

    product = db.get(Product, payload.product_id) if payload.product_id else None
    if payload.product_id and product is None:
        raise ProductNotFound(f"No product with id {payload.product_id}.")

    db.add(Feedback(
        user_id=user.id,
        session_id=payload.session_id,
        plan_id=payload.plan_id,
        product_id=payload.product_id,
        feedback_type=payload.feedback_type,
        comment=payload.comment,
    ))
    db.flush()

    preferences = preference_learning.record_signal(
        db, user, product, payload.feedback_type
    )
    db.commit()

    return FeedbackResponse(
        ok=True,
        preferences_updated=product is not None,
        updated_preferences=PreferencesOut(**preference_learning.as_dict(preferences)),
    )


@router.post("/interactions", response_model=FeedbackResponse)
def record_interaction(payload: InteractionRequest, db: DbSession,
                       user: CurrentUser) -> FeedbackResponse:
    """Implicit signals: viewed, clicked, saved.

    Kept separate from feedback so the admin metrics can tell an explicit
    opinion apart from a page view.
    """
    if payload.interaction_type not in VALID_INTERACTIONS:
        raise ValidationError(
            f"interaction_type must be one of {', '.join(sorted(VALID_INTERACTIONS))}."
        )

    product = db.get(Product, payload.product_id)
    if product is None:
        raise ProductNotFound(f"No product with id {payload.product_id}.")

    db.add(ProductInteraction(
        user_id=user.id,
        product_id=product.id,
        interaction_type=payload.interaction_type,
    ))
    db.flush()

    preferences = preference_learning.record_signal(
        db, user, product, payload.interaction_type
    )
    db.commit()

    return FeedbackResponse(
        ok=True,
        preferences_updated=True,
        updated_preferences=PreferencesOut(**preference_learning.as_dict(preferences)),
    )


@router.get("/saved", response_model=list[ProductOut])
def saved_products(db: DbSession, user: CurrentUser) -> list[ProductOut]:
    rows = db.scalars(
        select(Product)
        .join(Feedback, Feedback.product_id == Product.id)
        .where(Feedback.user_id == user.id, Feedback.feedback_type == FeedbackType.SAVED)
        .distinct()
    ).all()
    return [product_out(p) for p in rows]
