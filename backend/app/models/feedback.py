"""User feedback on recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.user import User


class Feedback(Base, IdMixin, TimestampMixin):
    __tablename__ = "feedback"

    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shopping_plans.id", ondelete="SET NULL")
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )

    feedback_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship(back_populates="feedback")
    product: Mapped[Product | None] = relationship()
