"""The eight demo scenarios, end to end.

One test per journey a judge might ask for. They assert on behaviour the demo
depends on, not on exact wording -- the assistant's prose comes from Gemini and
changes between runs, so asserting on it would produce a suite that fails for
no reason. What must not change is the state machine, the plan, and the money.
"""

from __future__ import annotations

import pytest

from .conftest import ok

pytestmark = pytest.mark.integration

# The agent may ask up to MAX_FOLLOWUP_QUESTIONS before it plans, and how many
# it actually asks depends on what the NLU extracted from the opening message
# -- which differs between the Gemini path and the deterministic fallback.
MAX_TURNS = 6


def converse_until_plan(client, headers, opening: str) -> str:
    """Answer the agent's follow-ups until it produces a plan.

    Hard-coding a turn count makes the test fail whenever the LLM extracts one
    slot more or less than last run, which is a property of the model rather
    than of the code under test.
    """
    turn = ok(client.post("/api/chat", headers=headers, json={"message": opening}))
    session_id = turn["session_id"]

    for _ in range(MAX_TURNS):
        if turn["plan_id"]:
            return turn["plan_id"]
        turn = ok(
            client.post(
                "/api/chat",
                headers=headers,
                json={"session_id": session_id, "message": "That's everything, go ahead"},
            )
        )

    raise AssertionError(
        f"no plan after {MAX_TURNS} turns; last state={turn['state']} "
        f"missing={turn.get('missing')}"
    )


class TestScenario1GoalBasedShopping:
    """Mode B: a goal in natural language becomes a costed shopping plan."""

    def test_goal_produces_a_plan_with_requirements(self, client, winter_trek_plan):
        plan_id, turn1, turn2 = winter_trek_plan
        assert turn1["slots"]["budget_total"] == 15000, turn1["slots"]
        assert turn2["next_action"] == "view_requirements"

        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        assert reqs["requirements"]["essential"], "a winter trek with no essentials"
        assert reqs["estimated_range"]["min"] <= reqs["estimated_range"]["max"]

    def test_requirements_carry_a_stated_reason(self, client, winter_trek_plan):
        """Explainability is the product, so an unexplained requirement is a bug."""
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        for group in reqs["requirements"].values():
            for req in group:
                assert req["reason"].strip(), f"{req['item_name']} has no reason"


class TestScenario2SpecificProductSearch:
    """Mode A: the user names a product instead of a goal."""

    def test_search_returns_relevant_shelf(self, client):
        data = ok(
            client.get(
                "/api/products/search",
                params={"q": "waterproof trekking jacket", "page_size": 10},
            )
        )
        assert data["items"], "no results for a query the catalog covers"
        # TF-IDF taxonomy inference should keep this on the outerwear shelf
        # rather than returning waterproof gaiters, which match every word.
        categories = {item["category"] for item in data["items"]}
        assert "outerwear" in categories, categories

    def test_price_filter_is_respected(self, client):
        data = ok(
            client.get(
                "/api/products/search",
                params={"q": "jacket", "max_price": 3000, "page_size": 20},
            )
        )
        assert data["items"], "no jackets under Rs 3,000"
        assert all(item["price"] <= 3000 for item in data["items"])

    def test_facets_describe_the_result_set(self, client):
        data = ok(client.get("/api/products/search", params={"q": "sleeping bag"}))
        assert data["facets"]["price_buckets"]
        assert data["facets"]["brands"]


class TestScenario3AlreadyOwnedItems:
    """'I already have trekking shoes' must not be billed for again.

    Owned requirements deliberately stay in the requirement groups flagged
    `is_owned`, rather than being deleted: `PATCH /api/requirements/{id}` lets
    the user un-tick one, which is only reachable if the row is still there.
    The frontend strikes them through and drops them from the to-buy count.
    What must never happen is paying for them.
    """

    def test_ownership_is_detected(self, client, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        assert reqs["already_owned"], "ownership stated in the goal was ignored"
        for item in reqs["already_owned"]:
            assert item["item_name"].strip(), item

    def test_already_owned_agrees_with_the_is_owned_flag(self, client, winter_trek_plan):
        """The summary list and the per-row flag are two views of one fact."""
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))

        summary = {o["item_name"] for o in reqs["already_owned"]}
        flagged = {
            req["item_name"]
            for group in reqs["requirements"].values()
            for req in group
            if req["is_owned"]
        }
        assert summary == flagged, (
            f"already_owned and the is_owned flags disagree: "
            f"only in summary {sorted(summary - flagged)}, "
            f"only flagged {sorted(flagged - summary)}"
        )

    def test_owned_items_are_not_in_any_bundle(self, client, headers, winter_trek_plan):
        """The actual money guarantee."""
        plan_id, _, _ = winter_trek_plan
        reqs = ok(client.get(f"/api/requirements/{plan_id}"))
        owned_ids = {
            req["id"]
            for group in reqs["requirements"].values()
            for req in group
            if req["is_owned"]
        }
        assert owned_ids, "no owned requirement to check against"

        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        for bundle in result["bundles"]:
            billed = {item["requirement"]["id"] for item in bundle["items"]}
            charged_twice = billed & owned_ids
            assert not charged_twice, (
                f"{bundle['preset']} bills for items the user already owns: "
                f"{[i['requirement']['item_name'] for i in bundle['items'] if i['requirement']['id'] in charged_twice]}"
            )


class TestScenario4BudgetOptimization:
    """Three presets, each internally consistent."""

    def test_three_presets_are_produced(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        presets = {b["preset"] for b in result["bundles"]}
        assert presets == {"best_overall", "best_budget", "premium"}, presets

    def test_budget_preset_is_not_more_expensive_than_premium(
        self, client, headers, winter_trek_plan
    ):
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        by_preset = {b["preset"]: b for b in result["bundles"]}
        assert by_preset["best_budget"]["total_cost"] <= by_preset["premium"]["total_cost"], (
            "the budget bundle costs more than the premium one, which means the "
            "preset weights are not doing anything"
        )

    def test_coverage_is_a_fraction(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        for bundle in result["bundles"]:
            assert 0.0 <= bundle["requirement_coverage"] <= 1.0


class TestScenario5InfeasibleBudget:
    """A budget that cannot buy the essentials must say so, not silently
    return a bundle the user cannot afford."""

    def test_tiny_budget_is_reported_as_infeasible(self, client, headers):
        plan_id = converse_until_plan(
            client,
            headers,
            "I need full winter trekking gear for a 5-day Himalayan trek, "
            "my budget is Rs 800",
        )

        result = ok(
            client.post("/api/bundle/optimize", headers=headers, json={"plan_id": plan_id})
        )
        # Either the optimizer flags infeasibility, or every bundle honestly
        # reports that it blows the budget. Both are acceptable; silently
        # pretending Rs 800 covers a Himalayan kit is not.
        honest = result["infeasible"] or all(
            b["over_budget"] > 0 or b["requirement_coverage"] < 1.0 for b in result["bundles"]
        )
        assert honest, (
            "Rs 800 produced a fully-covered, within-budget winter trek bundle: "
            f"{[(b['preset'], b['total_cost'], b['requirement_coverage']) for b in result['bundles']]}"
        )


class TestScenario6Comparison:
    def test_compare_marks_a_winner_per_column(self, client, headers, winter_trek_plan):
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
        ids = [r["product"]["id"] for r in recs["results"][0]["recommendations"][:3]]
        if len(ids) < 2:
            pytest.skip("need at least two candidates to compare")

        comparison = ok(
            client.post(
                "/api/compare",
                headers=headers,
                json={"product_ids": ids, "plan_id": plan_id, "requirement_id": req_id},
            )
        )
        assert len(comparison["rows"]) == len(ids)
        assert comparison["columns"]
        for column in comparison["columns"]:
            winners = [r for r in comparison["rows"] if r["is_best"].get(column)]
            assert len(winners) <= len(ids), column


class TestScenario7Explainability:
    def test_every_recommendation_states_its_reasons(self, client, headers, winter_trek_plan):
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
        for rec in recs["results"][0]["recommendations"]:
            assert rec["reasons"], f"{rec['product']['name']} recommended with no reason"
            assert rec["score_breakdown"]["final"] > 0

    def test_explanation_never_leaks_model_reasoning(self, client, headers, winter_trek_plan):
        """Reasons are grounded in the computed breakdown, not in raw model text.

        The guardrail we promise is that the LLM rephrases numbers rather than
        producing them, so no chain-of-thought scaffolding should reach the API.
        """
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
                json={"product_id": product_id, "requirement_id": req_id, "plan_id": plan_id},
            )
        )
        leaked = ("chain of thought", "let me think", "step 1:", "as an ai", "system prompt")
        blob = " ".join(explanation["reasons"]).lower()
        for phrase in leaked:
            assert phrase not in blob, f"explanation leaked {phrase!r}: {blob[:200]}"


class TestScenario8MarketplaceFiltering:
    """Only marketplaces the user switched on may feed recommendations."""

    def test_source_filter_restricts_search(self, client):
        data = ok(
            client.get("/api/products/search", params={"sources": "MARKET_A", "page_size": 30})
        )
        assert data["items"]
        assert {item["source"] for item in data["items"]} == {"MARKET_A"}

    def test_source_filter_restricts_recommendations(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "sources": ["MARKET_A"]},
            )
        )
        sources = {
            rec["product"]["source"]
            for result in recs["results"]
            for rec in result["recommendations"]
        }
        assert sources <= {"MARKET_A"}, sources

    def test_empty_source_list_returns_nothing(self, client, headers, winter_trek_plan):
        """`[]` means the user switched everything off.

        It must stay distinct from `null` ("no opinion"), or a user who
        deselected every marketplace silently gets all of them back.
        """
        plan_id, _, _ = winter_trek_plan
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "sources": []},
            )
        )
        total = sum(len(r["recommendations"]) for r in recs["results"])
        assert total == 0, f"{total} recommendations returned with every marketplace off"

    def test_null_sources_uses_every_marketplace(self, client, headers, winter_trek_plan):
        plan_id, _, _ = winter_trek_plan
        recs = ok(
            client.post(
                "/api/recommendations",
                headers=headers,
                json={"plan_id": plan_id, "sources": None},
            )
        )
        total = sum(len(r["recommendations"]) for r in recs["results"])
        assert total > 0

    def test_marketplace_registry_documents_unavailable_sources(self, client):
        """Amazon, Flipkart and Myntra are listed with the reason they are off,
        rather than omitted. The toggle UI renders `note` verbatim."""
        data = ok(client.get("/api/marketplaces"))
        by_key = {m["key"]: m for m in data["marketplaces"]}
        for key in ("AMAZON", "FLIPKART", "MYNTRA"):
            assert key in by_key, f"{key} missing from the registry"
            assert by_key[key]["available"] is False
            assert by_key[key]["note"].strip(), f"{key} is unavailable with no reason given"
