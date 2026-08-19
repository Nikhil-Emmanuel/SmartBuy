"""Load the curated catalog into the database.

    python -m scripts.seed              # incremental, safe to re-run
    python -m scripts.seed --reset      # drop catalog tables and reload
    python -m scripts.seed --interactions 15000

Run from the backend/ directory with the venv active.
Owner: Member 8 (DevOps) with Member 2 (Data).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.database import SessionLocal, init_db, new_id
from app.models.product import Offer, Product, ProductInteraction
from app.models.user import User, UserPreference

# Weighted so that "viewed" dominates, as it would in a real clickstream.
INTERACTION_WEIGHTS = {
    "viewed": 0.52,
    "clicked": 0.22,
    "liked": 0.10,
    "saved": 0.07,
    "purchased": 0.05,
    "disliked": 0.03,
    "not_interested": 0.01,
}


def load_catalog(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Catalog not found at {path}\n"
            f"Generate it first:  python scripts/generate_catalog.py"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def seed_products(db, payload: dict, reset: bool) -> int:
    if reset:
        db.execute(delete(ProductInteraction))
        db.execute(delete(Offer))
        db.execute(delete(Product))
        db.commit()
        print("  reset: catalog tables cleared")

    existing = db.scalar(select(func.count()).select_from(Product)) or 0
    if existing and not reset:
        print(f"  products already present ({existing}) -- skipping, use --reset to reload")
        return existing

    rows = []
    for p in payload["products"]:
        rows.append({
            "id": p["id"],
            "source": p["source"],
            "external_product_id": p["external_product_id"],
            "name": p["name"],
            "brand": p["brand"],
            "category": p["category"],
            "subcategory": p["subcategory"],
            "description": p["description"],
            "price": p["price"],
            "original_price": p["original_price"],
            "discount_pct": p["discount_pct"],
            "rating": p["rating"],
            "review_count": p["review_count"],
            "features": p["features"],
            "specs": p["specs"],
            "tags": p["tags"],
            "availability": p["availability"],
            "delivery_days": p["delivery_days"],
            "url": p["url"],
            "image_url": p["image_url"],
            "product_group_key": p["product_group_key"],
            "is_simulated": p["is_simulated"],
            "created_at": datetime.now(UTC),
        })
    db.bulk_insert_mappings(Product, rows)
    db.commit()
    print(f"  products         {len(rows)} inserted")
    return len(rows)


def seed_offers(db, payload: dict) -> int:
    if db.scalar(select(func.count()).select_from(Offer)):
        print("  offers already present -- skipping")
        return 0

    rows = []
    for o in payload["offers"]:
        rows.append({
            "id": new_id(),
            "product_id": o["product_id"],
            "offer_type": o["offer_type"],
            "discount_pct": o["discount_pct"],
            "flat_discount": o["flat_discount"],
            "coupon_code": o["coupon_code"],
            "description": o["description"],
            "valid_from": datetime.fromisoformat(o["valid_from"]),
            "valid_to": datetime.fromisoformat(o["valid_to"]),
        })
    db.bulk_insert_mappings(Offer, rows)
    db.commit()
    print(f"  offers           {len(rows)} inserted")
    return len(rows)


def seed_interactions(db, count: int, seed: int) -> int:
    """Synthetic clickstream for collaborative filtering and admin metrics.

    Clearly synthetic: labelled as such in the README and never presented as
    real user behaviour. Users are given category affinities so that CF has an
    actual signal to find rather than uniform noise.
    """
    if db.scalar(select(func.count()).select_from(ProductInteraction)):
        print("  interactions already present -- skipping")
        return 0

    rng = random.Random(seed)
    products = db.execute(
        select(Product.id, Product.category, Product.subcategory,
               Product.rating, Product.review_count, Product.price)
    ).all()
    if not products:
        print("  no products -- skipping interactions")
        return 0

    by_category: dict[str, list] = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)
    categories = list(by_category)

    # Popularity weight: more reviewed and better rated products get picked
    # more often, which is what makes a popularity baseline non-trivial.
    pop_weight = {
        p.id: math.log1p(p.review_count) * (0.5 + p.rating / 5.0) for p in products
    }

    n_users = max(50, count // 60)
    now = datetime.now(UTC)
    user_rows, pref_rows, inter_rows = [], [], []

    for _ in range(n_users):
        uid = new_id()
        affinity = rng.sample(categories, k=min(3, len(categories)))
        user_rows.append({
            "id": uid, "name": None, "email": None,
            "is_anonymous": True, "created_at": now - timedelta(days=rng.randint(1, 90)),
        })
        pref_rows.append({
            "id": new_id(), "user_id": uid,
            "preferred_categories": affinity, "preferred_brands": [],
            "min_price": None, "max_price": None,
            "price_bias": rng.choice(["value", "balanced", "premium"]),
            "delivery_bias": rng.choice(["fast", "standard"]),
            "brand_affinity": {}, "category_affinity": {}, "subcategory_affinity": {},
            "updated_at": now,
        })

        for _ in range(max(1, int(rng.gauss(count / n_users, 6)))):
            # 75% of activity inside the user's affinity categories.
            cat = rng.choice(affinity) if rng.random() < 0.75 else rng.choice(categories)
            pool = by_category[cat]
            weights = [pop_weight[p.id] for p in pool]
            product = rng.choices(pool, weights=weights, k=1)[0]
            itype = rng.choices(
                list(INTERACTION_WEIGHTS), weights=list(INTERACTION_WEIGHTS.values()), k=1
            )[0]
            inter_rows.append({
                "id": new_id(), "user_id": uid, "product_id": product.id,
                "interaction_type": itype,
                "created_at": now - timedelta(
                    days=rng.randint(0, 89), minutes=rng.randint(0, 1439)
                ),
            })

    db.bulk_insert_mappings(User, user_rows)
    db.bulk_insert_mappings(UserPreference, pref_rows)
    db.bulk_insert_mappings(ProductInteraction, inter_rows)
    db.commit()
    print(f"  synthetic users  {len(user_rows)} inserted")
    print(f"  interactions     {len(inter_rows)} inserted")
    return len(inter_rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="clear catalog tables first")
    ap.add_argument("--catalog", type=Path, default=Path(settings.CATALOG_PATH))
    ap.add_argument("--interactions", type=int, default=15000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--if-empty",
        action="store_true",
        help="do nothing when the catalog already has products (for container startup)",
    )
    args = ap.parse_args()

    print(f"Seeding {settings.DATABASE_URL.split('://')[0]} database...")
    init_db()

    if args.if_empty:
        # Container entrypoints run this on every boot. Reseeding a live
        # database on restart would rewrite product ids, and every plan and
        # recommendation already persisted points at the old ones.
        with SessionLocal() as db:
            existing = db.scalar(select(func.count()).select_from(Product))
        if existing:
            print(f"  catalog already has {existing} products -- nothing to do.")
            return 0

    payload = load_catalog(args.catalog)
    print(f"  catalog          {args.catalog.name} ({payload['count']} products)")

    with SessionLocal() as db:
        seed_products(db, payload, args.reset)
        seed_offers(db, payload)
        seed_interactions(db, args.interactions, args.seed)

        total = db.scalar(select(func.count()).select_from(Product))
        print(f"\nDone. {total} products in the database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
