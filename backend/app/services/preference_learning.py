"""Preference tracking.

Deliberately not machine learning: an exponentially-weighted counter over
feedback and interactions, clamped to [-1, 1]. Master prompt section 26 --
we describe this as preference *tracking*, and we do not claim long-term
learning we have not built. It feeds one of eight ranking components.

Formula (docs/DATA_MODEL.md section 5):
    liked / saved     -> brand +0.30, category +0.20, price band +0.15
    disliked          -> brand -0.30, category -0.15
    not_interested    -> subcategory -0.40
    decay 0.95 applied to every existing score on each update

Owner: Member 3 (ML).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.constants import FeedbackType, InteractionType
from app.models.product import Product
from app.models.user import User, UserPreference

log = logging.getLogger("smartbuy.preferences")

DECAY = 0.95
CLAMP = 1.0
# Below this the affinity is noise, and keeping it just grows the JSON blob.
PRUNE_BELOW = 0.02

DELTAS: dict[str, dict[str, float]] = {
    FeedbackType.RELEVANT: {"brand": 0.30, "category": 0.20},
    FeedbackType.SAVED: {"brand": 0.30, "category": 0.20},
    FeedbackType.NOT_RELEVANT: {"brand": -0.30, "category": -0.15},
    FeedbackType.NOT_INTERESTED: {"subcategory": -0.40},
    InteractionType.LIKED: {"brand": 0.30, "category": 0.20},
    InteractionType.DISLIKED: {"brand": -0.30, "category": -0.15},
    InteractionType.PURCHASED: {"brand": 0.30, "category": 0.20},
    InteractionType.CLICKED: {"brand": 0.05, "category": 0.05},
    InteractionType.VIEWED: {"brand": 0.02, "category": 0.02},
}

# How strongly a positive signal pulls the preferred price band.
PRICE_BAND_WEIGHT = 0.15


def ensure_preferences(db: Session, user: User) -> UserPreference:
    if user.preferences is None:
        preferences = UserPreference(user_id=user.id)
        db.add(preferences)
        db.flush()
        db.refresh(user)
    return user.preferences


def _apply(scores: dict, key: str, delta: float) -> dict:
    """Decay everything, then nudge one key. Returns a new dict.

    A new dict rather than in-place mutation: SQLAlchemy does not track
    mutations inside a plain JSON column, so an in-place update silently
    never persists.
    """
    updated = {k: round(v * DECAY, 4) for k, v in (scores or {}).items()}
    current = updated.get(key, 0.0)
    updated[key] = round(max(-CLAMP, min(CLAMP, current + delta)), 4)
    return {k: v for k, v in updated.items() if abs(v) >= PRUNE_BELOW}


def _blend(current: int | None, observed: int, weight: float) -> int:
    if current is None:
        return observed
    return round(current * (1 - weight) + observed * weight)


def record_signal(db: Session, user: User, product: Product | None,
                  signal: str) -> UserPreference:
    """Apply one feedback or interaction signal to the user's preferences."""
    preferences = ensure_preferences(db, user)
    deltas = DELTAS.get(signal)
    if product is None or not deltas:
        return preferences

    if "brand" in deltas:
        preferences.brand_affinity = _apply(
            preferences.brand_affinity, product.brand, deltas["brand"]
        )
    if "category" in deltas:
        preferences.category_affinity = _apply(
            preferences.category_affinity, product.category, deltas["category"]
        )
    if "subcategory" in deltas:
        preferences.subcategory_affinity = _apply(
            preferences.subcategory_affinity, product.subcategory, deltas["subcategory"]
        )

    positive = any(v > 0 for v in deltas.values())
    if positive:
        # The band the user actually engages with, not one they declared.
        preferences.min_price = _blend(
            preferences.min_price, int(product.price * 0.6), PRICE_BAND_WEIGHT
        )
        preferences.max_price = _blend(
            preferences.max_price, int(product.price * 1.6), PRICE_BAND_WEIGHT
        )

    # Explicit lists stay small and readable: they are shown in the profile UI.
    preferences.preferred_brands = _top_keys(preferences.brand_affinity, 6)
    preferences.preferred_categories = _top_keys(preferences.category_affinity, 6)

    db.flush()
    log.debug("Preferences updated for %s on %s", user.id, signal)
    return preferences


def _top_keys(scores: dict, limit: int) -> list[str]:
    positive = [(k, v) for k, v in (scores or {}).items() if v > 0.1]
    positive.sort(key=lambda kv: -kv[1])
    return [k for k, _ in positive[:limit]]


def as_dict(preferences: UserPreference | None) -> dict:
    if preferences is None:
        return {}
    return {
        "preferred_categories": list(preferences.preferred_categories or []),
        "preferred_brands": list(preferences.preferred_brands or []),
        "min_price": preferences.min_price,
        "max_price": preferences.max_price,
        "price_bias": preferences.price_bias,
        "delivery_bias": preferences.delivery_bias,
        "brand_affinity": dict(preferences.brand_affinity or {}),
        "category_affinity": dict(preferences.category_affinity or {}),
        "subcategory_affinity": dict(preferences.subcategory_affinity or {}),
    }
