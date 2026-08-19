"""Conformance to docs/API_CONTRACT.md v1.0 (frozen).

The contract is frozen, so these tests are the thing that keeps it frozen.
Each assertion corresponds to a promise the frontend was written against;
breaking one breaks a screen, not just a test.
"""

from __future__ import annotations

import pytest

from .conftest import ok


class TestMoneyAndScores:
    """Money is integer rupees. Scores are floats in [0, 1]. Never the reverse."""

    def test_prices_are_integers(self, client):
        data = ok(client.get("/api/products/search", params={"page_size": 20}))
        for item in data["items"]:
            for field in ("price", "original_price", "discount_pct"):
                assert isinstance(item[field], int), (
                    f"{field} is {type(item[field]).__name__}, not int -- a float "
                    f"here prints 'Rs 14999.999999' in the bundle total"
                )
            assert not isinstance(item["price"], bool), "bool is an int subclass"

    def test_scores_are_bounded_floats(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        req_id = reqs["requirements"]["essential"][0]["id"]

        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "requirement_ids": [req_id]},
            )
        )
        recommendations = recs["results"][0]["recommendations"]
        assert recommendations, "no recommendations for an essential requirement"

        for rec in recommendations:
            assert 0.0 <= rec["score"] <= 1.0, rec["score"]
            for component, value in rec["score_breakdown"].items():
                assert 0.0 <= value <= 1.0, f"{component}={value} outside [0, 1]"

    def test_ranks_are_dense_and_one_based(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        req_id = reqs["requirements"]["essential"][0]["id"]
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "requirement_ids": [req_id]},
            )
        )
        ranks = [r["rank"] for r in recs["results"][0]["recommendations"]]
        assert ranks == list(range(1, len(ranks) + 1)), ranks


class TestErrorEnvelope:
    """Every error is {error: {code, message, details}}. The frontend's
    ApiError parser depends on it and has no fallback."""

    @pytest.mark.parametrize(
        ("path", "code"),
        [
            ("/api/products/does-not-exist", "PRODUCT_NOT_FOUND"),
            ("/api/session/does-not-exist", "SESSION_NOT_FOUND"),
            ("/api/requirements/does-not-exist", "PLAN_NOT_FOUND"),
        ],
    )
    def test_not_found_envelope(self, client, path, code):
        response = client.get(path)
        assert response.status_code == 404
        body = response.json()
        assert set(body) == {"error"}, body
        assert body["error"]["code"] == code
        assert body["error"]["message"], "error with no human-readable message"

    def test_validation_error_envelope(self, client, headers):
        response = client.post("/api/chat", headers=headers, json={})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "VALIDATION_ERROR", body
        assert body["error"]["details"], "validation error with no details"


class TestSimulatedDataLabelling:
    """Demo pricing must never be presented as live marketplace data.

    This is a claim we make to users, so it is a test, not a convention.
    """

    def test_products_are_flagged_simulated(self, client):
        data = ok(client.get("/api/products/search", params={"page_size": 20}))
        assert all(item["is_simulated"] for item in data["items"])

    def test_explanation_evidence_is_flagged(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        req_id = reqs["requirements"]["essential"][0]["id"]
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "requirement_ids": [req_id]},
            )
        )
        product_id = recs["results"][0]["recommendations"][0]["product"]["id"]

        explanation = ok(
            client.post(
                "/api/explain",
                headers=headers,
                json={
                    "product_id": product_id,
                    "requirement_id": req_id,
                    "plan_id": plan_id,
                },
            )
        )
        assert explanation["evidence"]["is_simulated"] is True

    def test_scorecard_sums_to_one_hundred(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        req_id = reqs["requirements"]["essential"][0]["id"]
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "requirement_ids": [req_id]},
            )
        )
        product_id = recs["results"][0]["recommendations"][0]["product"]["id"]
        explanation = ok(
            client.post(
                "/api/explain",
                headers=headers,
                json={
                    "product_id": product_id,
                    "requirement_id": req_id,
                    "plan_id": plan_id,
                },
            )
        )
        total = sum(p["max"] for p in explanation["weighted_points"])
        assert abs(total - 100.0) < 0.5, f"scorecard maxima sum to {total}, not 100"


class TestBudgetArithmetic:
    def test_remaining_and_over_budget_are_never_both_set(
        self, client, headers, winter_trek_plan
    ):
        """`remaining_budget` is clamped at 0 and overage is reported separately.

        The frontend briefly derived overage from `abs(remaining_budget)` and
        displayed 'Over by Rs 0' on every over-budget bundle, because the
        clamp had already discarded the number it needed.
        """
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        for bundle in result["bundles"]:
            assert bundle["remaining_budget"] >= 0, bundle["remaining_budget"]
            assert bundle["over_budget"] >= 0, bundle["over_budget"]
            assert not (bundle["remaining_budget"] > 0 and bundle["over_budget"] > 0), (
                f"{bundle['preset']} reports both Rs {bundle['remaining_budget']} left "
                f"and Rs {bundle['over_budget']} over"
            )

    def test_bundle_total_equals_sum_of_line_totals(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        for bundle in result["bundles"]:
            expected = sum(item["line_total"] for item in bundle["items"])
            assert bundle["total_cost"] == expected, (
                f"{bundle['preset']}: total_cost {bundle['total_cost']} != "
                f"sum of line totals {expected}"
            )

    def test_line_total_is_unit_price_times_quantity(self, client, headers, winter_trek_plan):
        """The bundle header and the line items must agree.

        A quantity rule like `ceil(duration_days / 2)` means several items are
        not quantity 1, so a line total that ignored quantity would still look
        right for most of the bundle.
        """
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        checked = 0
        for bundle in result["bundles"]:
            for item in bundle["items"]:
                assert item["line_total"] == item["product"]["price"] * item["quantity"], (
                    f"{item['requirement']['item_name']}: line_total "
                    f"{item['line_total']} != {item['product']['price']} x {item['quantity']}"
                )
                checked += 1
        assert checked, "no bundle items to check"
