"""Product and offer response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.core.constants import SOURCE_DISPLAY_NAMES
from app.schemas.common import ORMModel


class OfferOut(ORMModel):
    id: str
    offer_type: str
    discount_pct: int = 0
    flat_discount: int = 0
    coupon_code: str | None = None
    description: str = ""
    valid_to: datetime | None = None


class ProductOut(ORMModel):
    id: str
    source: str
    source_name: str = ""
    external_product_id: str
    name: str
    brand: str
    category: str
    subcategory: str
    description: str = ""

    price: int
    original_price: int
    discount_pct: int = 0

    rating: float = 0.0
    review_count: int = 0

    features: list[str] = Field(default_factory=list)
    specs: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    availability: str
    delivery_days: int

    url: str = ""
    image_url: str = ""
    product_group_key: str = ""

    # Drives the "Simulated demo data" badge. Never hide this.
    is_simulated: bool = True

    @classmethod
    def from_model(cls, product) -> ProductOut:
        out = cls.model_validate(product)
        out.source_name = SOURCE_DISPLAY_NAMES.get(product.source, product.source)
        return out


class PriceBucket(ORMModel):
    label: str
    min_price: int
    max_price: int
    count: int


class SearchFacets(ORMModel):
    brands: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, int] = Field(default_factory=dict)
    categories: dict[str, int] = Field(default_factory=dict)
    price_buckets: list[PriceBucket] = Field(default_factory=list)


class ProductSearchResponse(ORMModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    facets: SearchFacets


class ProductDetailResponse(ORMModel):
    product: ProductOut
    offers: list[OfferOut] = Field(default_factory=list)
    # Same product_group_key on other marketplaces -- the cross-source row.
    other_sources: list[ProductOut] = Field(default_factory=list)
