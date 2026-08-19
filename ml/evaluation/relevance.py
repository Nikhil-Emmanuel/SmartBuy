"""Ground-truth relevance labels, derived from the requirement specification.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
We have no purchase logs, no click logs and no human relevance judgements --
the catalog is curated demo data and the product is a hackathon build. So this
is not a user-satisfaction evaluation and no number produced here should be
read as one.

What it *is*: a specification-conformance evaluation. The knowledge base states,
for each requirement, which shelf the item lives on (category/subcategory),
which features it must have, and roughly what it should cost. A product that
matches all three genuinely satisfies the stated need; one that does not,
does not. Asking "does the ranker put spec-satisfying products at the top of
the list?" is a real, falsifiable question, and it is the one we answer.

Known limitation, stated plainly: the ranker's `feature_match` and `budget_fit`
components read the same product attributes these labels are built from, so the
ranker and the labels are not independent. The headline lift over the baselines
is therefore an upper bound on ranking quality, not a neutral measurement.
The ablation study in run_eval.py exists to work around exactly this -- it
measures the components that the labels do *not* look at.
"""

from __future__ import annotations

# Widen the price band by this much before calling a product over-priced. The
# knowledge base ranges are estimates written by hand, not hard ceilings, and
# labelling a Rs 2,600 jacket irrelevant against a [800, 2500] estimate would
# be measuring the estimate rather than the ranker.
PRICE_TOLERANCE = 1.15

FULLY_RELEVANT = 2
PARTIALLY_RELEVANT = 1
NOT_RELEVANT = 0


def _has_required_features(product, required: list[str]) -> bool:
    if not required:
        return True
    have = {f.lower() for f in (product.features or [])}
    return {f.lower() for f in required} <= have


def _in_price_band(product, est_min: int, est_max: int) -> bool:
    if est_max <= 0:
        return True
    return product.price <= est_max * PRICE_TOLERANCE


def relevance_gain(product, item) -> int:
    """Graded relevance of `product` for knowledge-base item `item`.

    2 -- right shelf, every required feature present, priced in band.
    1 -- right shelf, but fails on features or on price.
    0 -- wrong shelf, or out of stock.

    Out of stock is 0 regardless of fit: a product you cannot buy does not
    satisfy a shopping requirement, and the ranker already penalises it.
    """
    if not product.in_stock:
        return NOT_RELEVANT

    on_shelf = (
        product.subcategory == item.subcategory
        if item.subcategory
        else product.category == item.category
    )
    if not on_shelf:
        return NOT_RELEVANT

    features_ok = _has_required_features(product, item.required_features)
    price_ok = _in_price_band(product, item.est_price_min, item.est_price_max)

    if features_ok and price_ok:
        return FULLY_RELEVANT
    return PARTIALLY_RELEVANT


def label_pool(products: list, item) -> list[int]:
    return [relevance_gain(p, item) for p in products]
