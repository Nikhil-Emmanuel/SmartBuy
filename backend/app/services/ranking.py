"""Personalized ranking engine.

Implements the weighted scorer from docs/ARCHITECTURE.md section 5. Every
component returns a float in [0, 1]; the final score is their weighted sum.

This module is pure Python and has no LLM dependency by design. The LLM is
never allowed to produce a score -- it only rephrases the numbers computed
here. That is what makes every recommendation defensible.

Owner: Member 3 (Recommendation/ML).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import settings
from app.core.constants import Availability

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
COMPONENTS = (
    "goal_suitability",
    "preference_match",
    "quality",
    "feature_match",
    "budget_fit",
    "review_strength",
    "delivery",
    "deal_value",
)


@dataclass(frozen=True)
class RankingConfig:
    weights: dict[str, float]
    presets: dict[str, dict[str, float]]
    budget_multipliers: dict[str, float]
    scoring: dict
    filters: dict

    def weights_for(self, preset: str | None) -> dict[str, float]:
        """Preset overrides replace base weights, then everything is
        renormalized so the vector still sums to 1.0."""
        if not preset or preset not in self.presets or not self.presets[preset]:
            return self.weights
        merged = {**self.weights, **self.presets[preset]}
        total = sum(merged.values()) or 1.0
        return {k: v / total for k, v in merged.items()}


@lru_cache(maxsize=1)
def get_ranking_config() -> RankingConfig:
    path = Path(settings.RANKING_CONFIG_PATH)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    weights = {k: float(v) for k, v in raw["weights"].items()}
    missing = set(COMPONENTS) - set(weights)
    if missing:
        raise ValueError(f"ranking.yaml is missing weights: {sorted(missing)}")

    total = sum(weights.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"ranking.yaml weights must sum to 1.0, got {total:.4f}")

    return RankingConfig(
        weights=weights,
        presets={k: {kk: float(vv) for kk, vv in (v or {}).items()}
                 for k, v in (raw.get("presets") or {}).items()},
        budget_multipliers={k: float(v)
                            for k, v in (raw.get("budget_multipliers") or {}).items()},
        scoring=raw.get("scoring") or {},
        filters=raw.get("filters") or {},
    )


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------
@dataclass
class ScoringContext:
    """Everything the scorer needs about the user and their goal.

    Deliberately decoupled from ORM objects so the scorer stays unit-testable
    without a database.
    """

    tags: set[str] = field(default_factory=set)
    budget_total: int | None = None
    price_bias: str = "balanced"
    delivery_bias: str = "standard"
    brand_affinity: dict[str, float] = field(default_factory=dict)
    category_affinity: dict[str, float] = field(default_factory=dict)
    subcategory_affinity: dict[str, float] = field(default_factory=dict)
    preferred_brands: list[str] = field(default_factory=list)
    preferred_categories: list[str] = field(default_factory=list)
    min_price: int | None = None
    max_price: int | None = None


@dataclass
class RequirementSpec:
    """The slice of a Requirement the scorer cares about."""

    item_name: str = ""
    category: str = ""
    subcategory: str = ""
    required_features: list[str] = field(default_factory=list)
    preferred_features: list[str] = field(default_factory=list)
    est_price_min: int = 0
    est_price_max: int = 0
    search_terms: list[str] = field(default_factory=list)


# Slot values -> catalog tag vocabulary. Keeps goal suitability grounded in
# the same words the catalog actually uses.
_SEASON_TAGS = {
    "winter": {"winter", "cold_weather", "snow"},
    "summer": {"summer", "sun_protection"},
    "monsoon": {"monsoon", "rain"},
    "autumn": {"trekking"},
    "spring": {"trekking"},
}
_REGION_TAGS = {
    "mountain": {"high_altitude", "trekking", "cold_weather"},
    "coastal": {"summer", "sun_protection"},
    "desert": {"summer", "sun_protection"},
    "urban": {"daily", "travel"},
    "forest": {"trekking", "camping"},
}
_ACTIVITY_TAGS = {
    "winter_trek": {"trekking", "winter", "cold_weather", "hiking"},
    "trek": {"trekking", "hiking", "outdoor"},
    "hiking": {"hiking", "trekking", "outdoor"},
    "camping": {"camping", "overnight", "outdoor"},
    "apartment_setup": {"apartment", "home_setup"},
    "hostel_setup": {"hostel", "home_setup", "student"},
    "laptop_purchase": {"programming", "work", "productivity"},
    "travel": {"travel", "daily"},
}


def derive_context_tags(context: dict) -> set[str]:
    """Turn the agent's slot dict into catalog tags."""
    tags: set[str] = set()

    activity = (context.get("activity") or "").lower()
    if activity:
        tags |= _ACTIVITY_TAGS.get(activity, {activity})

    season = (context.get("season") or "").lower()
    tags |= _SEASON_TAGS.get(season, set())

    region = (context.get("region_type") or "").lower()
    tags |= _REGION_TAGS.get(region, set())

    experience = (context.get("experience_level") or "").lower()
    if experience in ("beginner", "first_time"):
        tags.add("beginner")

    if context.get("camping"):
        tags |= {"camping", "overnight"}

    duration = context.get("duration_days")
    if isinstance(duration, int) and duration >= 3:
        tags.add("essentials")

    return tags


# --------------------------------------------------------------------------
# Individual components -- each returns [0, 1]
# --------------------------------------------------------------------------
def score_goal_suitability(product, req: RequirementSpec, ctx: ScoringContext) -> float:
    """Does this product actually serve the stated goal and conditions?"""
    ptags = {t.lower() for t in (product.tags or [])}
    if not ctx.tags:
        base = 0.6  # no context (Mode A): stay neutral rather than penalize
    else:
        overlap = len(ptags & ctx.tags)
        base = min(1.0, overlap / max(2.0, len(ctx.tags) * 0.55))

    # Category/subcategory agreement is a strong signal that this candidate
    # belongs to the requirement at all.
    if req.subcategory and product.subcategory == req.subcategory:
        base = base * 0.7 + 0.30
    elif req.category and product.category == req.category:
        base = base * 0.8 + 0.15

    return max(0.0, min(1.0, base))


def score_preference_match(product, ctx: ScoringContext) -> float:
    """Brand/category affinity plus price-bias agreement.

    Starts at a neutral 0.5 so a brand-new user is neither rewarded nor
    punished -- the cold-start case must not distort the ranking.
    """
    score = 0.5

    brand_aff = ctx.brand_affinity.get(product.brand, 0.0)
    score += brand_aff * 0.25
    if product.brand in ctx.preferred_brands:
        score += 0.15

    cat_aff = ctx.category_affinity.get(product.category, 0.0)
    sub_aff = ctx.subcategory_affinity.get(product.subcategory, 0.0)
    score += cat_aff * 0.12 + sub_aff * 0.12
    if product.category in ctx.preferred_categories:
        score += 0.08

    if ctx.min_price is not None and ctx.max_price is not None:
        if ctx.min_price <= product.price <= ctx.max_price:
            score += 0.10
        else:
            score -= 0.05

    tags = {t.lower() for t in (product.tags or [])}
    if ctx.price_bias == "value" and "value" in tags:
        score += 0.10
    elif ctx.price_bias == "premium" and "premium" in tags:
        score += 0.10

    if ctx.delivery_bias == "fast" and product.delivery_days <= 3:
        score += 0.05

    return max(0.0, min(1.0, score))


def score_quality(product, cfg: RankingConfig) -> float:
    """Rating, damped by review volume.

    A 5.0 from 3 reviews must not outrank a 4.5 from 2,800. The pivot controls
    how quickly we start trusting the rating.
    """
    pivot = float(cfg.scoring.get("review_confidence_pivot", 150))
    rating_norm = max(0.0, (product.rating - 2.5) / 2.5)  # 2.5->0, 5.0->1
    confidence = product.review_count / (product.review_count + pivot)
    # An unproven product regresses toward a neutral 0.5 rather than its rating.
    return max(0.0, min(1.0, rating_norm * confidence + 0.5 * (1 - confidence)))


def score_feature_match(product, req: RequirementSpec) -> float:
    pfeatures = {f.lower() for f in (product.features or [])}
    required = {f.lower() for f in req.required_features}
    preferred = {f.lower() for f in req.preferred_features}

    if not required and not preferred:
        return 0.6  # nothing specified: neutral, not zero

    required_score = len(pfeatures & required) / len(required) if required else 1.0
    preferred_score = len(pfeatures & preferred) / len(preferred) if preferred else 0.5

    return max(0.0, min(1.0, 0.7 * required_score + 0.3 * preferred_score))


def score_budget_fit(product, req: RequirementSpec, cfg: RankingConfig) -> float:
    """Peaks when the price sits at a sensible fraction of the item's ceiling.

    Rewards value without collapsing into "always pick the cheapest", which
    would make every bundle preset identical.
    """
    ceiling = req.est_price_max or 0
    if ceiling <= 0:
        return 0.5

    ideal_ratio = float(cfg.scoring.get("ideal_price_ratio", 0.75))
    overshoot = float(cfg.filters.get("max_price_overshoot", 1.35))

    ratio = product.price / ceiling
    if ratio > overshoot:
        return 0.0

    # Triangular falloff around the ideal ratio; cheap is good but suspiciously
    # cheap relative to the estimate is mildly penalized.
    if ratio <= ideal_ratio:
        span = ideal_ratio if ideal_ratio > 0 else 1.0
        return max(0.35, 0.35 + 0.65 * (ratio / span))
    span = max(1e-6, overshoot - ideal_ratio)
    return max(0.0, 1.0 - (ratio - ideal_ratio) / span)


def score_review_strength(product) -> float:
    """Review volume as an independent trust signal. log10-scaled: 10 reviews
    ~0.25, 1k ~0.75, 10k+ ~1.0."""
    if product.review_count <= 0:
        return 0.0
    return max(0.0, min(1.0, math.log10(product.review_count + 1) / 4.0))


def score_delivery(product, cfg: RankingConfig) -> float:
    fast = int(cfg.scoring.get("fast_delivery_days", 2))
    slow = int(cfg.scoring.get("slow_delivery_days", 10))
    if product.delivery_days <= fast:
        return 1.0
    if product.delivery_days >= slow:
        return 0.0
    return 1.0 - (product.delivery_days - fast) / max(1, slow - fast)


def score_deal_value(product, cfg: RankingConfig) -> float:
    """Discount depth, saturating.

    Capped because '70% off' on an inflated MRP is not 14x better than a fair
    5% off. We credit up to max_credited_discount_pct and no further.
    """
    cap = float(cfg.scoring.get("max_credited_discount_pct", 45))
    if cap <= 0:
        return 0.0
    return max(0.0, min(1.0, product.discount_pct / cap))


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------
def score_product(
    product,
    req: RequirementSpec,
    ctx: ScoringContext,
    preset: str | None = None,
    cfg: RankingConfig | None = None,
) -> dict[str, float]:
    """Return every component plus the weighted final score.

    The full breakdown is always returned: there is no score without its
    components, because the explanation layer is grounded in them.
    """
    cfg = cfg or get_ranking_config()
    weights = cfg.weights_for(preset)

    components = {
        "goal_suitability": score_goal_suitability(product, req, ctx),
        "preference_match": score_preference_match(product, ctx),
        "quality": score_quality(product, cfg),
        "feature_match": score_feature_match(product, req),
        "budget_fit": score_budget_fit(product, req, cfg),
        "review_strength": score_review_strength(product),
        "delivery": score_delivery(product, cfg),
        "deal_value": score_deal_value(product, cfg),
    }

    final = sum(components[k] * weights[k] for k in COMPONENTS)

    if product.availability == Availability.OUT_OF_STOCK:
        # Kept as a candidate so substitution can explain the swap, but it
        # must never win a ranking.
        final *= float(cfg.scoring.get("out_of_stock_penalty", 0.35))

    components["final"] = round(max(0.0, min(1.0, final)), 4)
    return {k: round(v, 4) for k, v in components.items()}


def weighted_points(breakdown: dict[str, float], preset: str | None = None) -> list[dict]:
    """Convert the breakdown into the Page 7 scorecard, scaled to 100 points."""
    cfg = get_ranking_config()
    weights = cfg.weights_for(preset)
    labels = {
        "goal_suitability": "Goal suitability",
        "preference_match": "Preference match",
        "quality": "Product quality",
        "feature_match": "Feature match",
        "budget_fit": "Budget fit",
        "review_strength": "Review strength",
        "delivery": "Delivery",
        "deal_value": "Deal value",
    }
    return [
        {
            "label": labels[c],
            "earned": round(breakdown.get(c, 0.0) * weights[c] * 100, 1),
            "max": round(weights[c] * 100, 1),
        }
        for c in COMPONENTS
    ]
