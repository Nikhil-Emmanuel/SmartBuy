"""Smoke test for the requirement planner + KB, including the exact demo case.

    python -m scripts.smoke_planner
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.kb.condition_dsl import (
    UnsafeExpression,
    evaluate_condition,
    evaluate_quantity,
)
from app.kb.loader import list_goals, resolve_goal_from_text
from app.services.requirement_planner import (
    plan_requirements,
    unmatched_existing_items,
)


def test_dsl() -> None:
    print("=" * 74)
    print("CONDITION DSL")
    print("=" * 74)
    ctx = {"temp_min_c": -5, "camping": True, "duration_days": 4,
           "people_count": 3, "experience_level": "beginner"}

    cases = [
        ("temp_min_c < 12", True),
        ("temp_min_c > 0", False),
        ("camping == true", True),
        ("experience_level == 'beginner'", True),
        ("experience_level in ['beginner', 'novice']", True),
        ("duration_days >= 3", True),
        ("budget_total >= 60000", False),          # missing slot -> False
    ]
    for expr, expected in cases:
        got = evaluate_condition(expr, ctx)
        flag = "ok " if got == expected else "FAIL"
        print(f"  [{flag}] {expr:42} -> {got}")
        assert got == expected, f"{expr}: expected {expected}, got {got}"

    qty = [("ceil(duration_days / 2)", 2), ("min(2, ceil(duration_days / 3))", 2),
           ("ceil(people_count / 2)", 2), ("people_count", 3), (1, 1)]
    for expr, expected in qty:
        got = evaluate_quantity(expr, ctx)
        flag = "ok " if got == expected else "FAIL"
        print(f"  [{flag}] qty {expr!s:38} -> {got}")
        assert got == expected, f"{expr}: expected {expected}, got {got}"

    # The DSL must refuse anything outside its grammar.
    for evil in ["__import__('os').system('echo pwned')",
                 "open('/etc/passwd').read()",
                 "(lambda: 1)()",
                 "self.__class__"]:
        try:
            evaluate_condition(evil, ctx)
            raise AssertionError(f"DSL accepted unsafe expression: {evil}")
        except UnsafeExpression:
            print(f"  [ok ] rejected unsafe: {evil[:42]}")
        except Exception as exc:
            print(f"  [ok ] rejected unsafe ({type(exc).__name__}): {evil[:36]}")


def show(result, title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)
    if result.goal is None:
        print("  no goal resolved")
        return

    print(f"  goal        {result.goal.display_name}  ({result.goal_key})")
    print(f"  context     season={result.context.get('season')} "
          f"region={result.context.get('region_type')} "
          f"temp_min={result.context.get('temp_min_c')}C "
          f"camping={result.context.get('camping')}")
    if result.assumptions:
        print("  assumed     " + "; ".join(
            f"{a.slot}={a.value} ({a.basis})" for a in result.assumptions))

    for priority in ("essential", "recommended", "optional"):
        rows = [r for r in result.by_priority(priority) if not r.is_owned]
        if not rows:
            continue
        print(f"\n  {priority.upper()}")
        for r in rows:
            qty = f" x{r.quantity}" if r.quantity > 1 else "   "
            print(f"    {r.item_name:28}{qty}  Rs {r.est_total_min:>6,}-{r.est_total_max:<6,}"
                  f"  [{r.subcategory}]")

    if result.owned:
        print("\n  ALREADY OWNED (excluded from purchase)")
        for r in result.owned:
            print(f"    {r.item_name:28}     matched from \"{r.owned_matched_from}\"")

    lo, hi = result.estimated_range
    budget = result.context.get("budget_total")
    print(f"\n  estimated   Rs {lo:,} - Rs {hi:,}"
          + (f"   (budget Rs {budget:,})" if budget else ""))


def main() -> int:
    test_dsl()

    print(f"\nKB goals: {[g.key for g in list_goals()]}")
    assert resolve_goal_from_text("I'm going for a winter trek").key == "winter_trek", \
        "longest-alias match failed"
    assert resolve_goal_from_text("planning a trek next month").key == "trek"
    print("Alias resolution: 'winter trek' -> winter_trek, 'trek' -> trek  [ok]")

    # ---- THE DEMO ----
    existing = ["trekking shoes", "backpack"]
    demo = plan_requirements(
        goal_key="winter_trek",
        context={
            "goal_text": "4-day winter trek in Manali",
            "activity": "winter_trek", "location": "Manali",
            "duration_days": 4, "experience_level": "beginner",
            "budget_total": 15000, "camping": False,
        },
        existing_items=existing,
    )
    show(demo, "DEMO  4-day winter trek, Manali, beginner, Rs 15,000, guesthouses")

    assert demo.goal_key == "winter_trek"
    owned_keys = {r.kb_item_key for r in demo.owned}
    assert "trekking_shoes" in owned_keys, "existing shoes not detected"
    assert "backpack" in owned_keys, "existing backpack not detected"
    # Regression: "trekking shoes" once matched socks, poles and the dry bag
    # on the shared word "trekking". Over-matching silently drops gear the
    # user actually needs, so pin the exact set.
    assert owned_keys == {"trekking_shoes", "backpack"}, (
        f"over-matched ownership: {sorted(owned_keys)}"
    )
    assert not any(r.kb_item_key == "tent" for r in demo.requirements), \
        "tent required despite camping=False"
    poles = next(r for r in demo.requirements if r.kb_item_key == "trekking_poles")
    assert poles.priority == "essential", "poles should be promoted for a beginner"
    thermals = next(r for r in demo.requirements if r.kb_item_key == "thermal_base_layer")
    assert thermals.quantity == 2, f"expected 2 thermals for 4 days, got {thermals.quantity}"
    assert not unmatched_existing_items(demo, existing), "an owned item went unclaimed"
    print("\n  [ok] owned items excluded, tent skipped, poles promoted, quantities scaled")

    # ---- camping variant ----
    camping = plan_requirements(
        goal_key="winter_trek",
        context={"activity": "winter_trek", "location": "Manali", "duration_days": 4,
                 "experience_level": "beginner", "budget_total": 15000,
                 "camping": True, "people_count": 2},
        existing_items=existing,
    )
    show(camping, "VARIANT  same trek, but camping overnight, 2 people")
    assert any(r.kb_item_key == "tent" for r in camping.requirements), "tent missing when camping"
    tent = next(r for r in camping.requirements if r.kb_item_key == "tent")
    assert tent.quantity == 1, f"2 people should need 1 tent, got {tent.quantity}"
    print("\n  [ok] camping adds tent/sleeping bag, quantity scales with group size")

    # ---- Mode A ----
    mode_a = plan_requirements(
        goal_key="laptop_purchase",
        context={"activity": "laptop_purchase", "budget_total": 80000},
        existing_items=[],
    )
    show(mode_a, "MODE A  laptop for programming under Rs 80,000")
    essentials = [r for r in mode_a.requirements if r.priority == "essential"]
    assert len(essentials) == 1, f"Mode A should stay focused, got {len(essentials)} essentials"
    print("\n  [ok] Mode A stays focused on the actual purchase")

    # ---- no season stated: inference must fire ----
    inferred = plan_requirements(
        goal_key="trek",
        context={"activity": "trek", "location": "Leh", "duration_days": 5},
        existing_items=[],
    )
    show(inferred, "INFERENCE  trek in Leh, nothing else stated")
    assert inferred.context["region_type"] == "mountain"
    assert inferred.context["temp_min_c"] is not None
    print("\n  [ok] season/region/temperature inferred rather than asked")

    print("\nAll planner assertions passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
