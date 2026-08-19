"""Turning a user's clickstream into one feature vector.

Shared by training (`ml/personalization/train.py`) and by serving
(`app/services/personalization.py`). FEATURE_NAMES is the contract between
them: the model is saved alongside the list it was fitted on, and serving
refuses to predict if the two disagree.

Everything here is computed from *observable behaviour* -- what the user
looked at, clicked, saved and bought. The segment label itself is never an
input; if it were, the model would score perfectly and mean nothing.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product, ProductInteraction

# Interaction types, in a fixed order so column positions are stable.
EVENT_TYPES = (
    "viewed", "clicked", "liked", "saved", "purchased", "disliked", "not_interested",
)

FEATURE_NAMES: tuple[str, ...] = (
    "n_events",
    *(f"rate_{t}" for t in EVENT_TYPES),
    "engagement_rate",      # clicked+liked+saved out of everything
    "conversion_rate",      # purchased out of everything
    "negative_rate",        # disliked+not_interested
    "mean_price",
    "median_price",
    "price_spread",
    "mean_discount",
    "max_discount",
    "mean_rating",
    "mean_review_count",
    "mean_delivery_days",
    "n_distinct_products",
    "n_distinct_categories",
    "n_distinct_brands",
    "brand_concentration",  # share of events on the single top brand
    "category_concentration",
    "purchase_mean_discount",
    "purchase_mean_price",
    "discount_gap",         # purchases vs browsing: do deals convert them?
)


@dataclass(frozen=True)
class UserFeatures:
    user_id: str
    values: list[float]
    n_events: int


def _safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _safe_mean(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _concentration(counter: Counter, total: int) -> float:
    """Share of activity on the single most frequent key.

    A blunt measure on purpose. Entropy would be more principled but is harder
    to read in a feature-importance table, and the thing being detected here --
    "this person keeps going back to the same brand" -- is exactly a top-share.
    """
    if not counter or not total:
        return 0.0
    return counter.most_common(1)[0][1] / total


def build_features(db: Session, user_ids: list[str] | None = None) -> list[UserFeatures]:
    """One row per user who has any recorded interaction.

    Users with no history are omitted rather than returned as a zero vector:
    there is nothing to personalise from, and a zero vector would be scored
    with the same confidence as a real one.
    """
    stmt = (
        select(
            ProductInteraction.user_id,
            ProductInteraction.interaction_type,
            Product.price,
            Product.discount_pct,
            Product.rating,
            Product.review_count,
            Product.delivery_days,
            Product.category,
            Product.brand,
            Product.id,
        )
        .join(Product, Product.id == ProductInteraction.product_id)
    )
    if user_ids is not None:
        if not user_ids:
            return []
        stmt = stmt.where(ProductInteraction.user_id.in_(user_ids))

    per_user: dict[str, list] = {}
    for row in db.execute(stmt):
        per_user.setdefault(row[0], []).append(row)

    out: list[UserFeatures] = []
    for user_id, events in per_user.items():
        out.append(UserFeatures(user_id, _vector(events), len(events)))
    return out


def _vector(events: list) -> list[float]:
    n = len(events)
    types = Counter(e[1] for e in events)
    prices = [float(e[2]) for e in events]
    discounts = [float(e[3]) for e in events]
    ratings = [float(e[4]) for e in events]
    reviews = [float(e[5]) for e in events]
    delivery = [float(e[6]) for e in events]
    categories = Counter(e[7] for e in events)
    brands = Counter(e[8] for e in events)
    products = {e[9] for e in events}

    purchases = [e for e in events if e[1] == "purchased"]
    purchase_discount = _safe_mean([float(e[3]) for e in purchases])
    browse_discount = _safe_mean(
        [float(e[3]) for e in events if e[1] in ("viewed", "clicked")]
    )

    rates = [types.get(t, 0) / n for t in EVENT_TYPES]
    engagement = sum(types.get(t, 0) for t in ("clicked", "liked", "saved")) / n
    conversion = types.get("purchased", 0) / n
    negative = sum(types.get(t, 0) for t in ("disliked", "not_interested")) / n

    return [
        float(n),
        *rates,
        engagement,
        conversion,
        negative,
        _safe_mean(prices),
        _median(prices),
        _stdev(prices),
        _safe_mean(discounts),
        max(discounts) if discounts else 0.0,
        _safe_mean(ratings),
        _safe_mean(reviews),
        _safe_mean(delivery),
        float(len(products)),
        float(len(categories)),
        float(len(brands)),
        _concentration(brands, n),
        _concentration(categories, n),
        purchase_discount,
        _safe_mean([float(e[2]) for e in purchases]),
        purchase_discount - browse_discount,
    ]
