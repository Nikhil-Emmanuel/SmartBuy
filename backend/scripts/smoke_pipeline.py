"""End-to-end pipeline smoke test: goal -> requirements -> products -> bundles.

    python -m scripts.smoke_pipeline

This is the demo, minus the LLM and the HTTP layer. If this passes, the core
product works.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.constants import BundlePreset  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.services.bundle_optimizer import optimize_presets, requirement_coverage  # noqa: E402
from app.services.product_search import get_search_service  # noqa: E402
from app.services.recommendation import (  # noqa: E402
    assign_badges,
    build_scoring_context,
    candidate_builder,
    rank_requirement,
)
from app.services.requirement_planner import plan_requirements  # noqa: E402

DEMO = {
    "goal_text": "4-day winter trek in Manali, beginner, budget Rs 15,000",
    "activity": "winter_trek",
    "location": "Manali",
    "duration_days": 4,
    "experience_level": "beginner",
    "budget_total": 15000,
    "camping": False,
    "people_count": 1,
}
EXISTING = ["trekking shoes", "backpack"]
BUDGET = DEMO["budget_total"]


def rupees(value: int) -> str:
    return f"Rs {value:,}"


def main() -> int:
    with SessionLocal() as db:
        get_search_service().warm(db)

        plan = plan_requirements("winter_trek", DEMO, EXISTING)
        to_buy = plan.to_buy
        print("=" * 78)
        print("GOAL   ", DEMO["goal_text"])
        print(f"        {len(plan.requirements)} requirements, "
              f"{len(plan.owned)} already owned, {len(to_buy)} to buy")
        print("=" * 78)

        ctx = build_scoring_context(plan.context)

        # ---- per-requirement comparison, the Page 5 payload ---------------
        sample = next(r for r in to_buy if r.kb_item_key == "insulated_jacket")
        candidates = rank_requirement(db, sample, plan.context, ctx)
        badges = assign_badges(candidates)
        print(f"\nCOMPARISON  {sample.item_name}  ({len(candidates)} candidates)")
        print(f"{'':2} {'score':>6} {'price':>9} {'rate':>5} {'dlv':>4} {'src':<9} {'badge':<14} name")
        shown = 0
        for c in candidates:
            badge = badges.get(c.product.id, "")
            if not badge and shown >= 4:
                continue
            shown += 1
            print(f"   {c.score:>6.3f} {rupees(c.product.price):>9} {c.product.rating:>5} "
                  f"{c.product.delivery_days:>3}d {c.product.source:<9} {badge:<14} "
                  f"{c.product.name[:34]}")
        assert len(set(badges.values())) >= 4, "badges collapsed onto too few products"

        top = candidates[0]
        print(f"\n  why {top.product.name[:44]}:")
        for reason in top.reasons:
            print(f"    - {reason}")
        assert top.reasons, "no evidence-based reasons generated"

        # ---- bundle optimization, the Page 6 payload ----------------------
        build = candidate_builder(db, to_buy, plan.context, ctx)
        bundles = optimize_presets(build, BUDGET)

        print("\n" + "=" * 78)
        print(f"BUNDLES   budget {rupees(BUDGET)}")
        print("=" * 78)
        for bundle in bundles:
            coverage = requirement_coverage(bundle, plan.requirements)
            flag = "  INFEASIBLE" if bundle.infeasible else ""
            money = (f"over {rupees(bundle.over_budget):>8}" if bundle.over_budget
                     else f"left {rupees(bundle.remaining_budget):>8}")
            print(f"\n  {bundle.preset.upper():<14} total {rupees(bundle.total_cost):>10}"
                  f"   saved {rupees(bundle.total_savings):>9}   {money}"
                  f"   avg-rating {bundle.avg_rating:.2f}"
                  f"   avg-item {rupees(bundle.avg_item_price):>8}"
                  f"   items {len(bundle.items):>2}"
                  f"   coverage {coverage:.0%}{flag}")
            for item in bundle.items[:6]:
                p = item.candidate.product
                print(f"      {item.requirement.item_name:26} x{item.quantity}  "
                      f"{rupees(item.line_total):>9}  {p.rating}*  {p.source}  {p.name[:30]}")
            if len(bundle.items) > 6:
                print(f"      ... and {len(bundle.items) - 6} more items")
            if bundle.excluded:
                print(f"      excluded: {', '.join(e['item_name'] for e in bundle.excluded[:5])}")

        overall = next(b for b in bundles if b.preset == BundlePreset.BEST_OVERALL)
        budget_b = next(b for b in bundles if b.preset == BundlePreset.BEST_BUDGET)
        premium = next(b for b in bundles if b.preset == BundlePreset.PREMIUM)

        # ---- substitution narrative --------------------------------------
        if overall.substitutions:
            print("\n  SUBSTITUTIONS made to fit the budget:")
            for sub in overall.substitutions[:4]:
                print(f"    {sub.requirement.item_name}: "
                      f"{sub.from_candidate.product.name[:26]} -> "
                      f"{sub.to_candidate.product.name[:26]}  "
                      f"({rupees(sub.price_delta)}, score {sub.score_delta:+.3f})")
                print(f"      {sub.reason}")

        # ---- assertions ---------------------------------------------------
        print("\n" + "=" * 78)
        assert not overall.infeasible, "best_overall should fit a Rs 15,000 budget"
        assert overall.total_cost <= BUDGET, (
            f"best_overall Rs {overall.total_cost} exceeds budget Rs {BUDGET}")
        assert budget_b.total_cost <= int(BUDGET * 0.70), (
            f"best_budget Rs {budget_b.total_cost} exceeds its 70% cap")
        assert budget_b.total_cost < overall.total_cost, "budget bundle is not cheaper"
        # Premium must buy demonstrably better core gear, not merely more items.
        # Compared on rating, which is preset-neutral: each bundle's own
        # utility_score uses its own weight vector and is not comparable.
        assert premium.avg_rating > budget_b.avg_rating, (
            f"premium avg rating {premium.avg_rating} should beat "
            f"budget {budget_b.avg_rating}")
        assert premium.avg_item_price > budget_b.avg_item_price, (
            "premium should buy more expensive core gear than the budget bundle")
        assert premium.total_cost > overall.total_cost, "premium should spend more"
        # Best value must leave the user some headroom rather than draining
        # the budget to the last rupee chasing marginal score.
        assert overall.remaining_budget >= int(BUDGET * 0.05), (
            f"best_overall left only Rs {overall.remaining_budget} of Rs {BUDGET}")
        assert overall.over_budget == 0 and budget_b.over_budget == 0, (
            "only premium may exceed the stated budget")
        assert requirement_coverage(overall, plan.requirements) == 1.0, (
            "best_overall must cover every essential requirement")
        for bundle in bundles:
            ids = [i.candidate.product.id for i in bundle.items]
            assert len(ids) == len(set(ids)), f"{bundle.preset} selected a duplicate product"
            assert all(i.candidate.in_stock for i in bundle.items), \
                f"{bundle.preset} selected an out-of-stock product"

        print("  [ok] all essentials covered, every bundle within its cap")
        print("  [ok] budget < overall < premium, no duplicates, nothing out of stock")

        # ---- infeasible path ----------------------------------------------
        tight = optimize_presets(build, 3000, presets=[BundlePreset.BEST_OVERALL])[0]
        print(f"\n  TIGHT BUDGET Rs 3,000 -> infeasible={tight.infeasible}, "
              f"shortfall {rupees(tight.shortfall)}, "
              f"{len(tight.items)} items kept, {len(tight.excluded)} excluded")
        assert tight.infeasible, "Rs 3,000 should be infeasible for this plan"
        assert tight.shortfall > 0 and tight.total_cost <= 3000
        assert tight.items, "an infeasible plan must still return something actionable"
        print("  [ok] infeasible budget degrades honestly instead of failing")

    print("\nPipeline smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
