"""Recommendation service -- the seam between planning, retrieval, scoring
and optimization.

Everything here is deterministic. Given the same catalog, requirements and
preferences, it returns the same answer every time, which is what makes the
demo rehearsable and the results defensible.

Owner: Member 3 (ML) with Member 4 (Optimization).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.constants import Availability, Badge, BundlePreset
from app.services.bundle_optimizer import Candidate, RequirementCandidates
from app.services.product_search import get_search_service
from app.services.ranking import (
    RequirementSpec,
    ScoringContext,
    derive_context_tags,
    score_product,
)
from app.services.requirement_planner import ADHOC_KEY

log = logging.getLogger("smartbuy.recommend")

CANDIDATE_POOL_SIZE = 40
# A "budget" pick has to still be a sensible product, not merely the cheapest
# thing that matched. This is the floor, relative to the best score found.
BUDGET_PICK_SCORE_FLOOR = 0.72
# Ratings are noisy below this many reviews; ignore them for "best rated".
MIN_REVIEWS_FOR_RATING_BADGE = 100


def build_scoring_context(context: dict, preferences=None) -> ScoringContext:
    """Combine goal context with the user's learned preferences.

    Privacy: only these derived signals ever reach the scorer, and none of
    them reach the LLM.
    """
    ctx = ScoringContext(
        tags=derive_context_tags(context),
        budget_total=context.get("budget_total"),
    )
    prefs = (context.get("preferences") or {}) if isinstance(context, dict) else {}
    ctx.price_bias = prefs.get("price_bias") or "balanced"
    ctx.delivery_bias = prefs.get("delivery_bias") or "standard"
    ctx.preferred_brands = list(prefs.get("brands") or [])

    if preferences is not None:
        ctx.price_bias = preferences.price_bias or ctx.price_bias
        ctx.delivery_bias = preferences.delivery_bias or ctx.delivery_bias
        ctx.preferred_brands = list(preferences.preferred_brands or ctx.preferred_brands)
        ctx.preferred_categories = list(preferences.preferred_categories or [])
        ctx.brand_affinity = dict(preferences.brand_affinity or {})
        ctx.category_affinity = dict(preferences.category_affinity or {})
        ctx.subcategory_affinity = dict(preferences.subcategory_affinity or {})
        ctx.min_price = preferences.min_price
        ctx.max_price = preferences.max_price

    return ctx


def to_spec(requirement) -> RequirementSpec:
    """Adapt either a PlannedRequirement or an ORM Requirement to the scorer."""
    return RequirementSpec(
        item_name=requirement.item_name,
        category=requirement.category,
        subcategory=requirement.subcategory or "",
        required_features=list(requirement.required_features or []),
        preferred_features=list(requirement.preferred_features or []),
        est_price_min=int(requirement.est_price_min or 0),
        est_price_max=int(requirement.est_price_max or 0),
        search_terms=list(requirement.search_terms or []),
        # "under Rs 3,000" came from the user, not from our price bands.
        hard_price_cap=getattr(requirement, "kb_item_key", "") == ADHOC_KEY,
    )


def build_reasons(product, breakdown: dict, spec: RequirementSpec, context: dict) -> list[str]:
    """Evidence-based bullets, derived only from computed values.

    This is the deterministic floor. The LLM may rewrite these into better
    prose, but it can never introduce a claim that is not already here.
    """
    reasons: list[str] = []

    if breakdown.get("goal_suitability", 0) >= 0.7:
        activity = (context.get("activity") or "your plan").replace("_", " ")
        reasons.append(f"Well suited to {activity}")

    matched = {f.lower() for f in (product.features or [])} & {
        f.lower() for f in spec.required_features
    }
    if matched:
        pretty = ", ".join(sorted(m.replace("_", " ") for m in matched))
        reasons.append(f"Matches your must-haves: {pretty}")

    if product.rating >= 4.2 and product.review_count >= 200:
        reasons.append(f"Rated {product.rating} across {product.review_count:,} reviews")
    elif product.rating >= 4.0:
        reasons.append(f"Rated {product.rating} by buyers")

    if product.discount_pct >= 15:
        saved = int(product.original_price) - int(product.price)
        reasons.append(f"{product.discount_pct}% off, saving Rs {saved:,}")

    if breakdown.get("budget_fit", 0) >= 0.8:
        reasons.append("Priced comfortably within your budget for this item")

    if product.delivery_days <= 2:
        reasons.append(f"Arrives in {product.delivery_days} day(s)")

    if product.availability == Availability.LOW_STOCK:
        reasons.append("Low stock at this price")

    return reasons[:5]


def rank_requirement(
    db: Session,
    requirement,
    context: dict,
    scoring_ctx: ScoringContext,
    preset: str | None = None,
    limit: int = CANDIDATE_POOL_SIZE,
    budget_ceiling: int | None = None,
    sources: list[str] | None = None,
) -> list[Candidate]:
    """Retrieve and score every candidate for one requirement, best first."""
    spec = to_spec(requirement)
    products = get_search_service().candidates_for_requirement(
        db, spec, limit=limit, budget_ceiling=budget_ceiling, sources=sources
    )
    if not products:
        return []

    candidates: list[Candidate] = []
    for product in products:
        breakdown = score_product(product, spec, scoring_ctx, preset=preset)
        candidates.append(
            Candidate(
                product=product,
                score=breakdown["final"],
                breakdown=breakdown,
                reasons=build_reasons(product, breakdown, spec, context),
            )
        )

    candidates.sort(key=lambda c: -c.score)
    return candidates


def assign_badges(candidates: list[Candidate]) -> dict[str, str]:
    """Map product_id -> badge. Each badge is awarded at most once.

    The five comparison categories from master prompt section 17. They must be
    genuinely different products where the catalog allows, or the comparison
    view is theatre.
    """
    pool = [c for c in candidates if c.product.availability != Availability.OUT_OF_STOCK]
    if not pool:
        return {}

    badges: dict[str, str] = {}
    taken: set[str] = set()

    def award(candidate: Candidate | None, badge: str) -> None:
        if candidate and candidate.product.id not in taken:
            badges[candidate.product.id] = badge
            taken.add(candidate.product.id)

    best = max(pool, key=lambda c: c.score)
    award(best, Badge.BEST_OVERALL)

    # Cheapest option that is still a defensible choice.
    floor = best.score * BUDGET_PICK_SCORE_FLOOR
    value_pool = [c for c in pool if c.score >= floor] or pool
    award(min(value_pool, key=lambda c: c.product.price), Badge.BEST_BUDGET)

    rated_pool = [c for c in pool if c.product.review_count >= MIN_REVIEWS_FOR_RATING_BADGE] or pool
    award(max(rated_pool, key=lambda c: (c.product.rating, c.product.review_count)),
          Badge.BEST_RATED)

    # Premium = the strongest product in the upper price half, not merely the
    # most expensive one.
    prices = sorted(c.product.price for c in pool)
    median = prices[len(prices) // 2]
    premium_pool = [c for c in pool if c.product.price >= median] or pool
    award(max(premium_pool, key=lambda c: (c.product.rating, c.score)), Badge.BEST_PREMIUM)

    award(max(pool, key=lambda c: (c.breakdown.get("deal_value", 0), c.score)), Badge.BEST_DEAL)

    return badges


def build_requirement_candidates(
    db: Session,
    requirements: list,
    context: dict,
    scoring_ctx: ScoringContext,
    preset: str | None = None,
    limit: int = CANDIDATE_POOL_SIZE,
    sources: list[str] | None = None,
) -> list[RequirementCandidates]:
    """Candidate sets for every requirement the user still needs to buy."""
    out: list[RequirementCandidates] = []
    for requirement in requirements:
        if getattr(requirement, "is_owned", False):
            continue
        candidates = rank_requirement(
            db, requirement, context, scoring_ctx, preset=preset, limit=limit, sources=sources
        )
        out.append(RequirementCandidates(requirement=requirement, candidates=candidates))
    return out


def candidate_builder(
    db: Session,
    requirements: list,
    context: dict,
    scoring_ctx: ScoringContext,
    limit: int = CANDIDATE_POOL_SIZE,
    sources: list[str] | None = None,
):
    """Return a callable for optimize_presets.

    Each preset rescores the same retrieved products with its own weights, so
    Budget and Premium genuinely disagree rather than differing only by cap.
    """
    cache: dict[str, list[RequirementCandidates]] = {}

    def build(preset: str) -> list[RequirementCandidates]:
        if preset not in cache:
            cache[preset] = build_requirement_candidates(
                db, requirements, context, scoring_ctx,
                preset=preset, limit=limit, sources=sources,
            )
        return cache[preset]

    return build


def find_substitutes(
    db: Session,
    requirement,
    context: dict,
    scoring_ctx: ScoringContext,
    current_product_id: str,
    reason: str = "cheaper",
    limit: int = 5,
) -> list[dict]:
    """Alternatives to a chosen product, ordered by the stated motivation."""
    candidates = rank_requirement(db, requirement, context, scoring_ctx)
    current = next((c for c in candidates if c.product.id == current_product_id), None)
    alternatives = [c for c in candidates if c.product.id != current_product_id]
    if not alternatives:
        return []

    if reason == "cheaper" and current:
        alternatives = [c for c in alternatives if c.product.price < current.price] or alternatives
        alternatives.sort(key=lambda c: (c.product.price, -c.score))
    elif reason == "better_rated":
        alternatives.sort(key=lambda c: (-c.product.rating, -c.score))
    elif reason == "faster_delivery":
        alternatives.sort(key=lambda c: (c.product.delivery_days, -c.score))
    else:  # unavailable, or anything else: best overall replacement
        alternatives.sort(key=lambda c: -c.score)

    out: list[dict] = []
    for alt in alternatives[:limit]:
        out.append({
            "candidate": alt,
            "price_delta": alt.price - current.price if current else 0,
            "score_delta": round(alt.score - current.score, 4) if current else 0.0,
            "why": _substitute_why(current, alt, reason),
        })
    return out


def _substitute_why(current: Candidate | None, alt: Candidate, reason: str) -> str:
    if current is None:
        return f"{alt.product.name} is the strongest available option for this requirement."

    delta = current.price - alt.price
    parts: list[str] = []
    if delta > 0:
        parts.append(f"Rs {delta:,} cheaper")
    elif delta < 0:
        parts.append(f"Rs {abs(delta):,} more")
    if alt.product.rating > current.product.rating:
        parts.append(f"better rated ({alt.product.rating} vs {current.product.rating})")
    if alt.product.delivery_days < current.product.delivery_days:
        parts.append(f"{current.product.delivery_days - alt.product.delivery_days} day(s) faster")

    shared = set(current.product.features or []) & set(alt.product.features or [])
    if len(shared) >= 2:
        parts.append(f"{len(shared)} shared key features")

    if reason == "unavailable":
        lead = "The original is out of stock. This replacement is"
    else:
        lead = "This alternative is"
    return f"{lead} {', '.join(parts) if parts else 'the closest match available'}."


def default_presets() -> list[str]:
    return [BundlePreset.BEST_OVERALL, BundlePreset.BEST_BUDGET, BundlePreset.PREMIUM]
