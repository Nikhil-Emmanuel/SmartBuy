"""End-to-end HTTP smoke test against the frozen API contract.

    python -m scripts.smoke_api

Walks the demo the way the frontend will: chat, requirements, recommendations,
compare, explain, bundles, plan, feedback, profile, admin. Every assertion
here is something the UI depends on.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

SESSION_ID = str(uuid.uuid4())
HEADERS = {"X-Session-Id": SESSION_ID}
ADMIN = {"X-Admin-Token": settings.ADMIN_TOKEN}

DEMO = ("I'm going for a 4-day winter trek in Manali, budget Rs 15,000, "
        "I'm a beginner, I already have trekking shoes and a backpack")


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def check(response, expected: int = 200):
    if response.status_code != expected:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path} -> "
            f"{response.status_code} (expected {expected}): {response.text[:400]}"
        )
    return response.json()


def main() -> int:
    with TestClient(app) as client:
        # ---- wave 1: health and products --------------------------------
        rule("WAVE 1  health + products")
        health = check(client.get("/api/health"))
        print(f"  health: {health}")
        assert health["status"] == "ok"
        assert health["catalog_size"] > 0, "no catalog -- run scripts/seed.py"

        search = check(client.get("/api/products/search",
                                  params={"q": "waterproof trekking jacket",
                                          "sort": "relevance", "page_size": 5}))
        print(f"  search: {search['total']} hits, "
              f"{len(search['facets']['brands'])} brands in facets")
        assert search["items"], "search returned nothing"
        assert search["facets"]["price_buckets"], "no price facets"
        first = search["items"][0]
        assert first["is_simulated"] is True, "demo data must be labelled"
        assert first["source_name"], "source display name missing"

        detail = check(client.get(f"/api/products/{first['id']}"))
        print(f"  detail: {detail['product']['name'][:44]} | "
              f"{len(detail['other_sources'])} other marketplace(s), "
              f"{len(detail['offers'])} offer(s)")

        offers = check(client.get("/api/offers", params={
            "product_ids": ",".join(p["id"] for p in search["items"][:5])}))
        assert len(offers["offers"]) == 5

        check(client.get("/api/products/does-not-exist"), 404)
        error = client.get("/api/products/does-not-exist").json()
        assert error["error"]["code"] == "PRODUCT_NOT_FOUND", error
        print("  [ok] error envelope shape confirmed")

        # ---- wave 2: chat -------------------------------------------------
        rule("WAVE 2  chat")
        turn1 = check(client.post("/api/chat", headers=HEADERS,
                                  json={"session_id": SESSION_ID, "message": DEMO}))
        print(f"  state={turn1['state']} next={turn1['next_action']} "
              f"degraded={turn1['degraded']}")
        print(f"  agent: {turn1['assistant_message']}")
        assert turn1["next_action"] == "answer_question"
        assert turn1["slots"]["budget_total"] == 15000
        assert turn1["missing"], "nothing reported as missing while asking"
        assert 0.0 <= turn1["progress"] <= 1.0

        turn2 = check(client.post("/api/chat", headers=HEADERS,
                                  json={"session_id": SESSION_ID,
                                        "message": "Camping overnight"}))
        print(f"  state={turn2['state']} next={turn2['next_action']} "
              f"plan_id={turn2['plan_id']}")
        print(f"  agent: {turn2['assistant_message']}")
        plan_id = turn2["plan_id"]
        assert plan_id, "no plan produced"
        assert turn2["next_action"] == "view_requirements"

        session = check(client.get(f"/api/session/{SESSION_ID}"))
        assert len(session["messages"]) == 4, session["messages"]
        assert session["plan_id"] == plan_id
        print(f"  [ok] session survives refresh: {len(session['messages'])} messages")

        check(client.get("/api/session/not-a-session"), 404)

        # ---- wave 3: requirements + recommendations -----------------------
        rule("WAVE 3  requirements + recommendations")
        requirements = check(client.get(f"/api/requirements/{plan_id}"))
        groups = requirements["requirements"]
        print(f"  {len(groups['essential'])} essential, "
              f"{len(groups['recommended'])} recommended, "
              f"{len(groups['optional'])} optional")
        print(f"  already owned: {[o['item_name'] for o in requirements['already_owned']]}")
        print(f"  estimate: Rs {requirements['estimated_range']['min']:,} - "
              f"Rs {requirements['estimated_range']['max']:,}")
        assert groups["essential"], "no essential requirements"
        assert requirements["already_owned"], "ownership was not honoured"

        sample = groups["essential"][0]
        recs = check(client.post("/api/recommendations", headers=HEADERS,
                                 json={"plan_id": plan_id,
                                       "requirement_ids": [sample["id"]],
                                       "limit_per_requirement": 5}))
        result = recs["results"][0]
        print(f"\n  {result['requirement']['item_name']}:")
        for rec in result["recommendations"]:
            print(f"    #{rec['rank']} {rec['score']:.3f} Rs {rec['product']['price']:>6,} "
                  f"{rec['product']['rating']}* {(rec['badge'] or ''):<13} "
                  f"{rec['product']['name'][:32]}")
        assert result["recommendations"], "no recommendations for an essential item"
        for rec in result["recommendations"]:
            assert rec["score_breakdown"]["final"] > 0, "score breakdown missing"
            assert rec["reasons"], "recommendation with no stated reason"
        print("  [ok] every recommendation carries a breakdown and reasons")

        # ---- wave 5: compare + explain ------------------------------------
        rule("WAVE 5  compare + explain")
        ids = [r["product"]["id"] for r in result["recommendations"][:3]]
        comparison = check(client.post("/api/compare", headers=HEADERS,
                                       json={"product_ids": ids, "plan_id": plan_id,
                                             "requirement_id": sample["id"]}))
        print(f"  columns: {comparison['columns']}")
        for row in comparison["rows"]:
            wins = [c for c, v in row["is_best"].items() if v]
            print(f"    {row['product']['name'][:34]:36} score {row['match_score']:.3f} "
                  f"wins {wins}")
        print(f"  winners: {comparison['winner']}")
        assert len(comparison["rows"]) == 3
        assert all(row["is_best"] for row in comparison["rows"]), "no per-column winners"

        explanation = check(client.post("/api/explain", headers=HEADERS,
                                        json={"product_id": ids[0],
                                              "requirement_id": sample["id"],
                                              "plan_id": plan_id}))
        total_max = sum(p["max"] for p in explanation["weighted_points"])
        earned = sum(p["earned"] for p in explanation["weighted_points"])
        print(f"\n  match {explanation['match_score']:.3f}  "
              f"scorecard {earned:.1f}/{total_max:.0f}  "
              f"llm_generated={explanation['llm_generated']}")
        for point in explanation["weighted_points"]:
            print(f"    {point['label']:20} {point['earned']:5.1f} / {point['max']:.0f}")
        for reason in explanation["reasons"]:
            print(f"    - {reason}")
        assert abs(total_max - 100.0) < 0.5, f"scorecard sums to {total_max}, not 100"
        assert explanation["evidence"]["is_simulated"] is True
        assert explanation["reasons"], "no explanation produced"
        print("  [ok] scorecard sums to 100 and evidence is labelled simulated")

        # ---- wave 4: bundles + plan ---------------------------------------
        rule("WAVE 4  bundles + shopping plan")
        optimized = check(client.post("/api/bundle/optimize", headers=HEADERS,
                                      json={"plan_id": plan_id}))
        for bundle in optimized["bundles"]:
            money = (f"over Rs {bundle['over_budget']:,}" if bundle["over_budget"]
                     else f"left Rs {bundle['remaining_budget']:,}")
            print(f"  {bundle['preset']:<14} Rs {bundle['total_cost']:>7,}  "
                  f"saved Rs {bundle['total_savings']:>6,}  {money:<18} "
                  f"items {len(bundle['items']):>2}  "
                  f"coverage {bundle['requirement_coverage']:.0%}"
                  f"{'  SELECTED' if bundle['is_selected'] else ''}")
        assert len(optimized["bundles"]) == 3
        assert optimized["infeasible"] is False

        substitutions = optimized["substitutions"]
        if substitutions:
            sub = substitutions[0]
            print(f"\n  substitution: {sub['item_name']} "
                  f"{sub['from']['name'][:24]} -> {sub['to']['name'][:24]} "
                  f"(Rs {sub['price_delta']:,})")
            print(f"    {sub['reason']}")

        selected = check(client.post("/api/bundle/select", headers=HEADERS,
                                     json={"plan_id": plan_id, "preset": "premium"}))
        assert selected["selected_preset"] == "premium"
        check(client.post("/api/bundle/select", headers=HEADERS,
                          json={"plan_id": plan_id, "preset": "best_overall"}))

        plan = check(client.get(f"/api/shopping-plan/{plan_id}"))
        totals = plan["totals"]
        print(f"\n  PLAN {plan['status']}  budget Rs {totals['budget']:,}  "
              f"total Rs {totals['estimated_total']:,}  "
              f"saved Rs {totals['savings']:,}  "
              f"remaining Rs {totals['remaining']:,}")
        print(f"  unfulfilled: {len(plan['unfulfilled'])}  "
              f"substitutions: {len(plan['substitutions'])}")
        assert plan["selected_preset"] == "best_overall"
        assert totals["estimated_total"] <= totals["budget"]
        assert plan["bundles"], "plan payload has no bundles"
        print("  [ok] the Page 6 payload is complete in one call")

        # ---- substitution --------------------------------------------------
        rule("SUBSTITUTION")
        item = next(i for b in plan["bundles"] if b["is_selected"] for i in b["items"])
        alternatives = check(client.post("/api/substitute", headers=HEADERS, json={
            "plan_id": plan_id,
            "requirement_id": item["requirement"]["id"],
            "current_product_id": item["product"]["id"],
            "reason": "cheaper",
        }))
        print(f"  {item['requirement']['item_name']} "
              f"(currently {item['product']['name'][:28]} at Rs {item['product']['price']:,})")
        for alt in alternatives["alternatives"][:3]:
            print(f"    Rs {alt['product']['price']:>6,}  {alt['price_delta']:>+7,}  "
                  f"{alt['product']['name'][:30]}")
            print(f"      {alt['why']}")
        assert alternatives["alternatives"], "no alternatives offered"

        # ---- wave 6: feedback, profile, admin -----------------------------
        rule("WAVE 6  feedback + profile + admin")
        liked = check(client.post("/api/feedback", headers=HEADERS, json={
            "product_id": ids[0], "plan_id": plan_id, "session_id": SESSION_ID,
            "feedback_type": "relevant",
        }))
        assert liked["preferences_updated"] is True
        check(client.post("/api/feedback", headers=HEADERS, json={
            "product_id": ids[1], "feedback_type": "saved"}))
        check(client.post("/api/interactions", headers=HEADERS, json={
            "product_id": ids[2], "interaction_type": "clicked"}))

        profile = check(client.get("/api/profile", headers=HEADERS))
        preferences = profile["preferences"]
        print(f"  brands: {preferences['preferred_brands']}")
        print(f"  categories: {preferences['preferred_categories']}")
        print(f"  price band: Rs {preferences['min_price']:,} - "
              f"Rs {preferences['max_price']:,}")
        print(f"  saved: {len(profile['saved_products'])}  "
              f"plans: {len(profile['recent_plans'])}  "
              f"feedback: {len(profile['feedback_history'])}")
        assert preferences["brand_affinity"], "no preference signal recorded"
        assert profile["saved_products"], "a saved product did not appear"
        assert profile["recent_plans"], "the plan is not on the profile"

        updated = check(client.put("/api/profile", headers=HEADERS,
                                   json={"price_bias": "value", "delivery_bias": "fast"}))
        assert updated["preferences"]["price_bias"] == "value"
        check(client.put("/api/profile", headers=HEADERS,
                         json={"price_bias": "nonsense"}), 422)
        print("  [ok] preference tracking updates and validates")

        check(client.get("/api/admin/metrics"), 401)
        metrics = check(client.get("/api/admin/metrics", headers=ADMIN))
        print(f"\n  ADMIN  users={metrics['users']} sessions={metrics['sessions']} "
              f"plans={metrics['plans_generated']} "
              f"recommendations={metrics['recommendations_generated']}")
        print(f"         avg bundle Rs {metrics['avg_bundle_value']:,}  "
              f"budget compliance {metrics['budget_compliance_rate']:.0%}  "
              f"coverage {metrics['requirement_coverage_avg']:.0%}")
        print(f"         llm calls={metrics['llm']['calls']} "
              f"fallback rate={metrics['llm']['fallback_rate']:.0%}  "
              f"catalog={metrics['catalog_size']:,}")
        print(f"         feedback={metrics['feedback']} "
              f"acceptance={metrics['recommendation_acceptance_rate']:.0%}")
        assert metrics["plans_generated"] >= 1
        assert metrics["catalog_size"] > 0
        assert metrics["feedback"], "feedback did not reach the metrics"

        logs = check(client.get("/api/admin/audit-logs",
                                headers=ADMIN, params={"limit": 5}))
        print(f"\n  audit: {logs['total']} entries")
        for entry in logs["logs"][:5]:
            print(f"    {entry['action']:<18} {(entry['tool'] or '-'):<14} "
                  f"{entry['status']:<9} {entry['latency_ms']:>5}ms  "
                  f"{entry['output_summary'][:36]}")
        assert logs["total"] > 0, "nothing was audited"
        print("  [ok] admin metrics are real aggregates, audit trail is populated")

        # ---- infeasible budget, honestly -----------------------------------
        rule("INFEASIBLE BUDGET")
        tight_session = str(uuid.uuid4())
        check(client.post("/api/chat", headers={"X-Session-Id": tight_session},
                          json={"session_id": tight_session,
                                "message": "planning a 5-day winter trek in Leh, "
                                           "budget Rs 2,000, first time"}))
        tight = check(client.post("/api/chat", headers={"X-Session-Id": tight_session},
                                  json={"session_id": tight_session,
                                        "message": "guesthouses"}))
        tight_plan = check(client.get(f"/api/shopping-plan/{tight['plan_id']}"))
        print(f"  agent: {tight['assistant_message']}")
        print(f"  status={tight_plan['status']}  "
              f"total Rs {tight_plan['totals']['estimated_total']:,}  "
              f"unfulfilled={len(tight_plan['unfulfilled'])}")
        assert tight_plan["status"] == "budget_infeasible", tight_plan["status"]
        assert tight_plan["totals"]["estimated_total"] <= 2000
        assert tight_plan["unfulfilled"], "nothing reported as unaffordable"
        assert any(b["items"] for b in tight_plan["bundles"]), \
            "an infeasible plan must still show something actionable"
        print("  [ok] returns 200 with an honest shortfall, not an error")

    print("\nAPI smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
