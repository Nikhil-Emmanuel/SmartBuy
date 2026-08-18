"""User and preference models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DeliveryBias, PriceBias
from app.db.database import Base, IdMixin, TimestampMixin, utcnow

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.plan import ShoppingPlan
    from app.models.product import ProductInteraction


class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    # No auth in v1 (ADR-005). Every visitor becomes an anonymous user row so
    # that preferences and feedback still have somewhere to live.
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    preferences: Mapped[UserPreference | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    plans: Mapped[list[ShoppingPlan]] = relationship(back_populates="user")
    interactions: Mapped[list[ProductInteraction]] = relationship(back_populates="user")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="user")


class UserPreference(Base, IdMixin):
    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    preferred_categories: Mapped[list] = mapped_column(JSON, default=list)
    preferred_brands: Mapped[list] = mapped_column(JSON, default=list)

    min_price: Mapped[int | None] = mapped_column(Integer)
    max_price: Mapped[int | None] = mapped_column(Integer)

    price_bias: Mapped[str] = mapped_column(String(16), default=PriceBias.BALANCED)
    delivery_bias: Mapped[str] = mapped_column(String(16), default=DeliveryBias.STANDARD)

    # Signed affinity scores in [-1, 1], keyed by name. Written by
    # services/preference_learning.py. See docs/DATA_MODEL.md section 5.
    brand_affinity: Mapped[dict] = mapped_column(JSON, default=dict)
    category_affinity: Mapped[dict] = mapped_column(JSON, default=dict)
    subcategory_affinity: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="preferences")
