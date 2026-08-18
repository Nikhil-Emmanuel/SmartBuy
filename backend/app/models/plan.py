"""Shopping plan and its derived requirements."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import FulfillmentStatus, PlanStatus, Priority
from app.db.database import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.recommendation import PlanBundle, Recommendation, Substitution
    from app.models.session import ChatSession
    from app.models.user import User


class ShoppingPlan(Base, IdMixin, TimestampMixin):
    __tablename__ = "shopping_plans"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL"), index=True
    )

    goal: Mapped[str] = mapped_column(Text, nullable=False)
    goal_summary: Mapped[str] = mapped_column(Text, default="")
    goal_key: Mapped[str | None] = mapped_column(String(64))  # resolved KB goal

    budget_total: Mapped[int | None] = mapped_column(Integer)
    estimated_total: Mapped[int] = mapped_column(Integer, default=0)
    estimated_savings: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="INR")

    # Frozen copy of the slots at generation time. A plan must stay
    # reproducible even after the user edits the session afterwards.
    context: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(24), default=PlanStatus.DRAFT)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)

    requirements: Mapped[list[Requirement]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    bundles: Mapped[list[PlanBundle]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    substitutions: Mapped[list[Substitution]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    session: Mapped[ChatSession | None] = relationship(back_populates="plans")
    user: Mapped[User | None] = relationship(back_populates="plans")


class Requirement(Base, IdMixin):
    """One thing the user needs in order to accomplish their goal."""

    __tablename__ = "requirements"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shopping_plans.id", ondelete="CASCADE"), index=True
    )

    kb_item_key: Mapped[str | None] = mapped_column(String(64))
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    subcategory: Mapped[str] = mapped_column(String(64), default="")

    priority: Mapped[str] = mapped_column(String(16), default=Priority.ESSENTIAL, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text, default="")

    est_price_min: Mapped[int] = mapped_column(Integer, default=0)
    est_price_max: Mapped[int] = mapped_column(Integer, default=0)

    search_terms: Mapped[list] = mapped_column(JSON, default=list)
    required_features: Mapped[list] = mapped_column(JSON, default=list)
    preferred_features: Mapped[list] = mapped_column(JSON, default=list)

    # Set when the user already owns this. Excluded from purchase, still shown.
    is_owned: Mapped[bool] = mapped_column(Boolean, default=False)
    owned_matched_from: Mapped[str | None] = mapped_column(String(120))

    fulfillment_status: Mapped[str] = mapped_column(
        String(24), default=FulfillmentStatus.PENDING
    )
    unfulfilled_reason: Mapped[str | None] = mapped_column(String(32))

    plan: Mapped[ShoppingPlan] = relationship(back_populates="requirements")
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="requirement", cascade="all, delete-orphan"
    )
