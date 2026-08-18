"""Catalog models: normalized product, offers, interactions.

Every source is transformed into Product by Member 2's ETL. Nothing downstream
ever sees a raw source row. See docs/DATA_MODEL.md section 1.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Availability
from app.db.database import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Product(Base, IdMixin, TimestampMixin):
    """Normalized product. Money is integer rupees -- never float.

    A budget optimizer working in floats prints "Rs 14999.999999" on stage.
    """

    __tablename__ = "products"

    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_product_id: Mapped[str] = mapped_column(String(64), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subcategory: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")

    price: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    original_price: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct: Mapped[int] = mapped_column(Integer, default=0)

    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    features: Mapped[list] = mapped_column(JSON, default=list)
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list] = mapped_column(JSON, default=list)

    availability: Mapped[str] = mapped_column(String(16), default=Availability.IN_STOCK)
    delivery_days: Mapped[int] = mapped_column(Integer, default=5)

    url: Mapped[str] = mapped_column(String(512), default="")
    image_url: Mapped[str] = mapped_column(String(512), default="")

    # Rows sharing this key are the same product listed on different
    # marketplaces. This is what makes cross-source price comparison real
    # rather than decorative.
    product_group_key: Mapped[str] = mapped_column(String(64), index=True, default="")

    # True for every curated/simulated row. Drives the demo-data badge in the
    # UI. We never present simulated pricing as if it were live.
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    offers: Mapped[list[Offer]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_products_cat_sub", "category", "subcategory"),
        Index("ix_products_source_ext", "source", "external_product_id", unique=True),
    )

    @property
    def savings(self) -> int:
        return max(0, self.original_price - self.price)

    @property
    def in_stock(self) -> bool:
        return self.availability != Availability.OUT_OF_STOCK


class Offer(Base, IdMixin):
    __tablename__ = "offers"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    offer_type: Mapped[str] = mapped_column(String(24), nullable=False)
    discount_pct: Mapped[int] = mapped_column(Integer, default=0)
    flat_discount: Mapped[int] = mapped_column(Integer, default=0)
    coupon_code: Mapped[str | None] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(String(255), default="")
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product: Mapped[Product] = relationship(back_populates="offers")


class ProductInteraction(Base, IdMixin, TimestampMixin):
    """Implicit + explicit signals. Feeds collaborative filtering and the
    preference tracker."""

    __tablename__ = "product_interactions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    interaction_type: Mapped[str] = mapped_column(String(24), nullable=False)

    user: Mapped[User] = relationship(back_populates="interactions")
