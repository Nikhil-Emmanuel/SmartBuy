"""Smoke test for retrieval + ranking, independent of the API layer.

    python -m scripts.smoke_search

Exercises the exact path the agent will use: requirement -> candidates ->
scored -> ranked, for the Manali winter-trek demo context.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.product_search import SearchFilters, get_search_service
from app.services.ranking import (
    RequirementSpec,
    ScoringContext,
    derive_context_tags,
    get_ranking_config,
    score_product,
    weighted_points,
)

DEMO_CONTEXT = {
    "activity": "winter_trek",
    "location": "Manali",
    "region_type": "mountain",
    "season": "winter",
    "duration_days": 4,
    "experience_level": "beginner",
    "budget_total": 15000,
    "camping": True,
}

REQUIREMENTS = [
    RequirementSpec(
        item_name="Thermal Base Layer", category="clothing", subcategory="thermals",
        required_features=["thermal"], preferred_features=["quick_dry", "lightweight"],
        est_price_min=800, est_price_max=2500,
        search_terms=["thermal base layer", "winter thermals", "merino base layer"],
    ),
    RequirementSpec(
        item_name="Insulated Trekking Jacket", category="outerwear", subcategory="jacket",
        required_features=["insulated"], preferred_features=["waterproof", "windproof"],
        est_price_min=2000, est_price_max=6000,
        search_terms=["insulated trekking jacket", "winter mountain jacket"],
    ),
    RequirementSpec(
        item_name="Trekking Poles", category="equipment", subcategory="trekking_poles",
        required_features=["adjustable"], preferred_features=["shock_absorbing", "lightweight"],
        est_price_min=700, est_price_max=2500,
        search_terms=["trekking poles", "hiking poles anti shock"],
    ),
    RequirementSpec(
        item_name="Headlamp", category="navigation", subcategory="headlamp",
        required_features=[], preferred_features=["rechargeable", "waterproof"],
        est_price_min=400, est_price_max=2000,
        search_terms=["rechargeable led headlamp", "head torch trekking"],
    ),
]


def main() -> int:
    cfg = get_ranking_config()
    print(f"Ranking weights: {cfg.weights}\n")

    svc = get_search_service()
    with SessionLocal() as db:
        size = svc.warm(db)
        print(f"Semantic index: {size} products\n")

        # --- Mode A: keyword search ---------------------------------------
        print("=" * 74)
        print('MODE A  "waterproof trekking shoes under Rs 3,000"')
        print("=" * 74)
        rows, total, facets = svc.search(
            db,
            SearchFilters(q="waterproof trekking shoes", max_price=3000,
                          exclude_out_of_stock=True),
            sort="relevance", page=1, page_size=5,
        )
        print(f"{total} matches. Top 5:")
        for p in rows:
            print(f"  Rs {p.price:>7,}  {p.rating}*  {p.source}  {p.name[:52]}")
        print(f"  sources: {facets['sources']}\n")

        # --- Mode B: goal-driven requirement ranking ----------------------
        ctx = ScoringContext(
            tags=derive_context_tags(DEMO_CONTEXT),
            budget_total=DEMO_CONTEXT["budget_total"],
            price_bias="balanced",
        )
        print("=" * 74)
        print("MODE B  4-day winter trek, Manali, beginner, Rs 15,000")
        print(f"context tags: {sorted(ctx.tags)}")
        print("=" * 74)

        for req in REQUIREMENTS:
            candidates = svc.candidates_for_requirement(db, req, limit=40)
            scored = [(p, score_product(p, req, ctx)) for p in candidates]
            scored = [s for s in scored if s[0].availability != "out_of_stock"]
            scored.sort(key=lambda s: -s[1]["final"])

            print(f"\n{req.item_name}  ({len(candidates)} candidates)")
            for p, b in scored[:3]:
                print(f"   {b['final']:.3f}  Rs {p.price:>6,}  {p.rating}*  "
                      f"{p.review_count:>6,} rev  {p.delivery_days}d  "
                      f"{p.source}  {p.name[:44]}")

            if scored:
                _top, breakdown = scored[0]
                pts = weighted_points(breakdown)
                detail = "  ".join(f"{d['label'].split()[0]} {d['earned']:.1f}/{d['max']:.0f}"
                                   for d in pts)
                print(f"      -> {detail}")
                print(f"      -> total {sum(d['earned'] for d in pts):.1f}/100")

    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
