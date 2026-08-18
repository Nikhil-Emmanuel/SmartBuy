"""Recommendations, bundles and substitutions.

A plan holds three switchable bundles (best_overall / best_budget / premium),
so bundle totals cannot live on the plan row itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.plan import Requirement, ShoppingPlan
    from app.models.product import Product


class Recommendation(Base, IdMixin, TimestampMixin):
    __tablename__ = "recommendations"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shopping_plans.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )

    score: Mapped[float] = mapped_column(Float, default=0.0)
    rank: Mapped[int] = mapped_column(Integer, default=0)
    badge: Mapped[str | None] = mapped_column(String(24))

    # The eight weighted components. Never null -- there is no score without
    # its components, because the explanation layer is grounded in them.
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)

    plan: Mapped[ShoppingPlan] = relationship(back_populates="recommendations")
    requirement: Mapped[Requirement] = relationship(back_populates="recommendations")
    product: Mapped[Product] = relationship()


class PlanBundle(Base, IdMixin, TimestampMixin):
    __tablename__ = "plan_bundles"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shopping_plans.id", ondelete="CASCADE"), index=True
    )
    preset: Mapped[str] = mapped_column(String(24), nullable=False)

    total_cost: Mapped[int] = mapped_column(Integer, default=0)
    total_savings: Mapped[int] = mapped_column(Integer, default=0)
    remaining_budget: Mapped[int] = mapped_column(Integer, default=0)
    utility_score: Mapped[float] = mapped_column(Float, default=0.0)
    requirement_coverage: Mapped[float] = mapped_column(Float, default=0.0)

    is_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[list] = mapped_column(JSON, default=list)

    plan: Mapped[ShoppingPlan] = relationship(back_populates="bundles")
    items: Mapped[list[BundleItem]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan"
    )


class BundleItem(Base, IdMixin):
    __tablename__ = "bundle_items"

    bundle_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plan_bundles.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE")
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE")
    )

    quantity: Mapped[int] = mapped_column(Integer, default=1)
    line_total: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[list] = mapped_column(JSON, default=list)

    bundle: Mapped[PlanBundle] = relationship(back_populates="items")
    requirement: Mapped[Requirement] = relationship()
    product: Mapped[Product] = relationship()


class Substitution(Base, IdMixin, TimestampMixin):
    """Every swap the optimizer makes is recorded here.

    This is what powers the "we replaced A with B because..." narrative.
    """

    __tablename__ = "substitutions"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shopping_plans.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("requirements.id", ondelete="CASCADE")
    )
    from_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE")
    )
    to_product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE")
    )

    price_delta: Mapped[int] = mapped_column(Integer, default=0)
    score_delta: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")

    plan: Mapped[ShoppingPlan] = relationship(back_populates="substitutions")
    from_product: Mapped[Product] = relationship(foreign_keys=[from_product_id])
    to_product: Mapped[Product] = relationship(foreign_keys=[to_product_id])
