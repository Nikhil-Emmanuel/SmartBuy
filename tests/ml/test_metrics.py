"""Metric correctness, checked against hand-worked arithmetic.

The evaluation numbers in ml/evaluation/results/ are only worth quoting if the
metrics behind them are right, so every formula here is verified against a
value computed by hand in the test rather than by re-implementing the same
function a second way.
"""

from __future__ import annotations

import math

import pytest
from evaluation.metrics import (
    dcg_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class TestPrecision:
    def test_counts_relevant_in_top_k(self):
        # [2, 0, 1] -> two of the first three are relevant at threshold 1
        assert precision_at_k([2, 0, 1], 3) == pytest.approx(2 / 3)

    def test_threshold_two_only_counts_fully_relevant(self):
        assert precision_at_k([2, 0, 1], 3, threshold=2) == pytest.approx(1 / 3)

    def test_divides_by_k_not_by_list_length(self):
        # A ranker returning one good item where ten were asked for is not
        # perfectly precise. Dividing by len() would report 1.0 here.
        assert precision_at_k([2], 5) == pytest.approx(0.2)

    def test_k_zero_is_zero_not_a_crash(self):
        assert precision_at_k([2, 2], 0) == 0.0


class TestRecall:
    def test_fraction_of_pool_relevants_retrieved(self):
        assert recall_at_k([2, 0, 1], 3, total_relevant=4) == pytest.approx(0.5)

    def test_threshold_applies_to_numerator(self):
        assert recall_at_k([2, 0, 1], 3, total_relevant=4, threshold=2) == pytest.approx(0.25)

    def test_no_relevant_in_pool_is_zero(self):
        assert recall_at_k([0, 0], 2, total_relevant=0) == 0.0


class TestDcgNdcg:
    def test_dcg_matches_hand_computation(self):
        # (2^2-1)/log2(2) + (2^0-1)/log2(3) + (2^1-1)/log2(4)
        expected = 3 / 1.0 + 0 / math.log2(3) + 1 / 2.0
        assert dcg_at_k([2, 0, 1], 3) == pytest.approx(expected)
        assert dcg_at_k([2, 0, 1], 3) == pytest.approx(3.5)

    def test_ndcg_matches_hand_computation(self):
        # ideal order [2, 1, 0] -> 3/1 + 1/log2(3) + 0 = 3.63093
        ideal = 3 / 1.0 + 1 / math.log2(3)
        assert ndcg_at_k([2, 0, 1], 3, [2, 1, 0]) == pytest.approx(3.5 / ideal)

    def test_perfect_order_is_one(self):
        assert ndcg_at_k([2, 1, 0], 3, [2, 1, 0]) == pytest.approx(1.0)

    def test_normalises_against_the_pool_not_its_own_output(self):
        # A ranker that returned only irrelevant items must score 0, even
        # though sorting its own gains would make them look "ideal".
        assert ndcg_at_k([0, 0], 2, ideal_gains=[2, 1, 0, 0]) == 0.0

    def test_pool_with_no_relevant_items_is_zero_not_division_by_zero(self):
        assert ndcg_at_k([0, 0], 2, ideal_gains=[0, 0]) == 0.0

    def test_order_matters(self):
        good = ndcg_at_k([2, 1, 0], 3, [2, 1, 0])
        bad = ndcg_at_k([0, 1, 2], 3, [2, 1, 0])
        assert good > bad


class TestReciprocalRank:
    def test_first_relevant_at_rank_three(self):
        assert reciprocal_rank([0, 0, 1]) == pytest.approx(1 / 3)

    def test_threshold_skips_partial_matches(self):
        assert reciprocal_rank([1, 2], threshold=2) == pytest.approx(0.5)

    def test_no_relevant_item_is_zero(self):
        assert reciprocal_rank([0, 0, 0]) == 0.0


def test_mean_of_empty_is_zero():
    assert mean([]) == 0.0
