"""Ranking metrics.

Pure functions over a list of graded relevance gains, in ranked order. No
dependency on the catalog, the database or the scorer, so they can be unit
tested against hand-worked examples -- which tests/ml/test_metrics.py does.

Gains are graded integers (see relevance.py): 2 = fully satisfies the
requirement spec, 1 = partially, 0 = not relevant.

The binary metrics (precision, recall, MRR) need a cutoff, which `threshold`
supplies. It is not always 1: when the candidate pool is already restricted to
one subcategory, nearly every product scores at least 1 and a threshold of 1
reports ~1.0 for every ranker including random. Raising the bar to 2 there is
what makes the metric able to separate them at all.
"""

from __future__ import annotations

import math


def precision_at_k(gains: list[int], k: int, threshold: int = 1) -> float:
    """Fraction of the top k that are relevant.

    Divided by k rather than by len(top_k) so a short result list is penalised
    for being short -- returning 3 good items when 10 were asked for is not
    perfect precision.
    """
    if k <= 0:
        return 0.0
    top = gains[:k]
    return sum(1 for g in top if g >= threshold) / k


def recall_at_k(gains: list[int], k: int, total_relevant: int, threshold: int = 1) -> float:
    """Fraction of all relevant items in the pool that made the top k."""
    if total_relevant <= 0:
        return 0.0
    return sum(1 for g in gains[:k] if g >= threshold) / total_relevant


def dcg_at_k(gains: list[int], k: int) -> float:
    """Discounted cumulative gain with the exponential gain formulation.

    (2^g - 1) rather than plain g, so the difference between a fully relevant
    item and a partially relevant one is worth more than the difference
    between partial and irrelevant. That matches how a shopper reads a list:
    a wrong-but-plausible product at rank 1 is a real failure.
    """
    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains[:k]))


def ndcg_at_k(gains: list[int], k: int, ideal_gains: list[int] | None = None) -> float:
    """DCG normalised by the best achievable DCG for this query.

    `ideal_gains` is the full pool's gains sorted descending. It must come from
    the pool, not from `gains`: normalising against the ranker's own output
    would score a ranker that returned only its 10 worst items as perfect.
    """
    ideal = sorted(ideal_gains if ideal_gains is not None else gains, reverse=True)
    best = dcg_at_k(ideal, k)
    if best <= 0:
        return 0.0
    return dcg_at_k(gains, k) / best


def reciprocal_rank(gains: list[int], threshold: int = 1) -> float:
    """1 / rank of the first relevant item; 0 if there is none."""
    for i, g in enumerate(gains):
        if g >= threshold:
            return 1.0 / (i + 1)
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
