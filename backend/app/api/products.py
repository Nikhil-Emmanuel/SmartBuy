"""Product search, detail and offers. API contract section 3.

Wave 1: this is what unblocks the frontend's product surfaces, so it ships
first and depends on nothing but the catalog.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.serializers import product_out
from app.core.errors import ProductNotFound
from app.models.product import Offer, Product
from app.schemas.product import (
    OfferOut,
    ProductDetailResponse,
    ProductSearchResponse,
    SearchFacets,
)
from app.services.product_search import SORT_KEYS, SearchFilters, get_search_service

router = APIRouter(prefix="/api/products", tags=["products"])
# `/api/offers` sits outside the /api/products prefix in the frozen contract.
offers_router = APIRouter(prefix="/api", tags=["products"])

MAX_PAGE_SIZE = 50
MAX_OFFER_LOOKUP = 50


@router.get("/search", response_model=ProductSearchResponse)
def search_products(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    category: str | None = None,
    subcategory: str | None = None,
    brand: str | None = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    source: str | None = None,
    features: Annotated[str | None, Query(description="Comma-separated")] = None,
    in_stock_only: bool = False,
    sort: str = "relevance",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> ProductSearchResponse:
    filters = SearchFilters(
        q=q,
        category=category,
        subcategory=subcategory,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        source=source,
        features=[f.strip() for f in features.split(",") if f.strip()] if features else None,
        exclude_out_of_stock=in_stock_only,
    )
    if sort not in SORT_KEYS and sort != "relevance":
        sort = "relevance"

    items, total, facets = get_search_service().search(
        db, filters, sort=sort, page=page, page_size=page_size
    )
    return ProductSearchResponse(
        items=[product_out(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        facets=SearchFacets(**facets),
    )


@offers_router.get("/offers")
def get_offers(
    db: DbSession,
    product_ids: Annotated[str, Query(description="Comma-separated product ids")],
) -> dict:
    """Offers for a batch of products, keyed by product id.

    Batched because the results grid needs offers for every card at once, and
    one request per card is how a demo starts feeling slow.
    """
    ids = [pid.strip() for pid in product_ids.split(",") if pid.strip()][:MAX_OFFER_LOOKUP]
    if not ids:
        return {"offers": {}}

    rows = db.scalars(select(Offer).where(Offer.product_id.in_(ids))).all()

    grouped: dict[str, list] = {pid: [] for pid in ids}
    for offer in rows:
        grouped[offer.product_id].append(OfferOut.model_validate(offer))
    return {"offers": grouped}


@router.get("/{product_id}", response_model=ProductDetailResponse)
def get_product(product_id: str, db: DbSession) -> ProductDetailResponse:
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFound(f"No product with id {product_id}.")

    offers = db.scalars(select(Offer).where(Offer.product_id == product.id)).all()

    # The cross-marketplace price row: the same product, other sources.
    others: list[Product] = []
    if product.product_group_key:
        others = list(db.scalars(
            select(Product)
            .where(Product.product_group_key == product.product_group_key,
                   Product.id != product.id)
            .order_by(Product.price)
        ))

    return ProductDetailResponse(
        product=product_out(product),
        offers=[OfferOut.model_validate(o) for o in offers],
        other_sources=[product_out(p) for p in others],
    )
