"""Rankers under comparison.

Every ranker receives the identical candidate pool and returns it reordered.
Nothing is filtered out: a ranker that hides bad products would score well by
returning three items, and the metrics deliberately punish short lists.

The interesting baseline is `semantic`. Popularity and rating are the standard
non-personalized straw men, but TF-IDF retrieval is what the system would fall
back to if the weighted scorer were deleted, so beating it is the claim that
actually matters.
"""

from __future__ import annotations

import random

from app.services.product_search import get_search_service
from app.services.ranking import RankingConfig, RequirementSpec, ScoringContext, score_product


def rank_smartbuy(
    products: list,
    spec: RequirementSpec,
    ctx: ScoringContext,
    cfg: RankingConfig,
    weights: dict[str, float] | None = None,
) -> list:
    """The production weighted scorer.

    `weights` overrides the configured vector; the ablation study uses it to
    zero one component at a time.
    """
    if weights is None:
        scored = [(score_product(p, spec, ctx, cfg=cfg)["final"], p) for p in products]
    else:
        scored = []
        for p in products:
            breakdown = score_product(p, spec, ctx, cfg=cfg)
            final = sum(breakdown[k] * w for k, w in weights.items())
            scored.append((final, p))
    # Ties broken by review count so the order is deterministic across runs --
    # otherwise two runs of the same eval report different NDCG.
    scored.sort(key=lambda sp: (-sp[0], -sp[1].review_count, sp[1].id))
    return [p for _, p in scored]


def rank_popularity(products: list, **_) -> list:
    return sorted(products, key=lambda p: (-p.review_count, p.id))


def rank_rating(products: list, **_) -> list:
    return sorted(products, key=lambda p: (-p.rating, -p.review_count, p.id))


def rank_price_asc(products: list, **_) -> list:
    return sorted(products, key=lambda p: (p.price, p.id))


def rank_semantic(products: list, spec: RequirementSpec, **_) -> list:
    """TF-IDF cosine against the requirement's search terms."""
    query = " ".join(spec.search_terms or [spec.item_name])
    if not query.strip():
        return list(products)
    service = get_search_service()
    allowed = {p.id for p in products}
    ranked = service.index.query(query, top_k=len(products), allowed_ids=allowed)
    order = {pid: i for i, (pid, _) in enumerate(ranked)}
    # Products TF-IDF gave zero similarity keep their pool order behind the
    # matches, rather than being dropped.
    return sorted(products, key=lambda p: (order.get(p.id, 10**6), p.id))


def rank_random(products: list, seed: int = 0, **_) -> list:
    shuffled = list(products)
    random.Random(seed).shuffle(shuffled)
    return shuffled
