"""Profile and preferences. API contract section 6.

ADR-005: there is no authentication. The client's X-Session-Id doubles as an
anonymous user id, which is enough to keep preferences and history attached to
a browser without asking anyone to sign up for a hackathon demo.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import product_out
from app.core.constants import DeliveryBias, FeedbackType, PriceBias
from app.core.errors import ValidationError
from app.models.feedback import Feedback
from app.models.plan import ShoppingPlan
from app.models.product import Product
from app.schemas.feedback import (
    FeedbackHistoryOut,
    PlanSummaryOut,
    PreferencesOut,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.services import preference_learning

router = APIRouter(prefix="/api", tags=["profile"])

RECENT_PLANS = 10
RECENT_FEEDBACK = 20


@router.get("/profile", response_model=ProfileResponse)
def get_profile(db: DbSession, user: CurrentUser) -> ProfileResponse:
    preferences = preference_learning.ensure_preferences(db, user)

    saved = db.scalars(
        select(Product)
        .join(Feedback, Feedback.product_id == Product.id)
        .where(Feedback.user_id == user.id, Feedback.feedback_type == FeedbackType.SAVED)
        .distinct()
    ).all()

    plans = db.scalars(
        select(ShoppingPlan)
        .where(ShoppingPlan.user_id == user.id)
        .order_by(ShoppingPlan.created_at.desc())
        .limit(RECENT_PLANS)
    ).all()

    history = db.scalars(
        select(Feedback)
        .where(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc())
        .limit(RECENT_FEEDBACK)
    ).all()

    db.commit()

    return ProfileResponse(
        user_id=user.id,
        is_anonymous=user.is_anonymous,
        preferences=PreferencesOut(**preference_learning.as_dict(preferences)),
        saved_products=[product_out(p) for p in saved],
        recent_plans=[
            PlanSummaryOut(
                plan_id=p.id,
                goal=p.goal,
                status=p.status,
                estimated_total=p.estimated_total,
                budget_total=p.budget_total,
                created_at=p.created_at,
            )
            for p in plans
        ],
        feedback_history=[
            FeedbackHistoryOut(
                product=product_out(f.product) if f.product else None,
                feedback_type=f.feedback_type,
                created_at=f.created_at,
            )
            for f in history
        ],
    )


@router.put("/profile", response_model=ProfileResponse)
def update_profile(payload: ProfileUpdateRequest, db: DbSession,
                   user: CurrentUser) -> ProfileResponse:
    preferences = preference_learning.ensure_preferences(db, user)

    if payload.price_bias is not None:
        if payload.price_bias not in {p.value for p in PriceBias}:
            raise ValidationError(f"Unknown price_bias '{payload.price_bias}'.")
        preferences.price_bias = payload.price_bias

    if payload.delivery_bias is not None:
        if payload.delivery_bias not in {d.value for d in DeliveryBias}:
            raise ValidationError(f"Unknown delivery_bias '{payload.delivery_bias}'.")
        preferences.delivery_bias = payload.delivery_bias

    if payload.preferred_categories is not None:
        preferences.preferred_categories = payload.preferred_categories[:12]
    if payload.preferred_brands is not None:
        preferences.preferred_brands = payload.preferred_brands[:12]

    if payload.min_price is not None:
        preferences.min_price = payload.min_price
    if payload.max_price is not None:
        preferences.max_price = payload.max_price
    if (preferences.min_price is not None and preferences.max_price is not None
            and preferences.min_price > preferences.max_price):
        raise ValidationError("min_price cannot be greater than max_price.")

    db.commit()
    return get_profile(db, user)
