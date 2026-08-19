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

# --------------------------------------------------------------------------
# Shopper segments
# --------------------------------------------------------------------------
# Each synthetic user is assigned one latent segment, which then drives which
# products they look at and how often they convert. The personalisation model
# (ml/personalization/) is trained to recover this segment from behaviour
# alone.
#
# This structure had to be added. The previous generator stored a `price_bias`
# on every user and then never used it: products were drawn by popularity only
# and the interaction type was drawn independently of the product. Measured on
# that data, users who bought heavily-discounted items and users who did not
# had indistinguishable browsing histories (mean discount 17.1 vs 16.9, mean
# rating 3.86 vs 3.86), so there was no pattern for any model to find.
#
# Because the segment is generated rather than observed, a model that recovers
# it is evidence the pipeline works end to end -- not evidence about how real
# shoppers behave. docs/PERSONALIZATION.md states this plainly and so must any
# presentation of the numbers.
SEGMENTS = {
    # Chases discounts; buys cheap; converts well when the deal is good.
    "deal_seeker": {
        "discount_pull": 3.0, "price_pull": -1.2, "rating_pull": 0.2,
        "brand_focus": 0, "purchase_rate": 1.0, "view_rate": 1.0,
    },
    # Buys on quality and does not need a discount to convert.
    "premium_buyer": {
        "discount_pull": -0.8, "price_pull": 1.6, "rating_pull": 2.2,
        "brand_focus": 0, "purchase_rate": 1.1, "view_rate": 0.8,
    },
    # Concentrates on a couple of brands; price-neutral.
    "brand_loyal": {
        "discount_pull": 0.2, "price_pull": 0.0, "rating_pull": 0.8,
        "brand_focus": 2, "purchase_rate": 1.0, "view_rate": 0.9,
    },
    # Browses a great deal and rarely commits: the segment worth nudging.
    "window_shopper": {
        "discount_pull": 1.0, "price_pull": 0.3, "rating_pull": 0.5,
        "brand_focus": 0, "purchase_rate": 0.15, "view_rate": 1.8,
    },
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
        select(Product.id, Product.category, Product.subcategory, Product.brand,
               Product.rating, Product.review_count, Product.price,
               Product.discount_pct)
    ).all()
    if not products:
        print("  no products -- skipping interactions")
        return 0

    by_category: dict[str, list] = {}
    for p in products:
        by_category.setdefault(p.category, []).append(p)
    categories = list(by_category)
    brands = sorted({p.brand for p in products})

    # Popularity weight: more reviewed and better rated products get picked
    # more often, which is what makes a popularity baseline non-trivial.
    pop_weight = {
        p.id: math.log1p(p.review_count) * (0.5 + p.rating / 5.0) for p in products
    }
    # Normalisers so the segment pulls below are comparable across dimensions.
    max_price = max(p.price for p in products) or 1
    log_max_price = math.log1p(max_price)

    def segment_weight(product, seg: dict, favourite_brands: set[str]) -> float:
        """How strongly this segment is drawn to this product.

        Multiplicative on top of popularity, and floored above zero so that no
        product becomes unreachable -- a segment that *never* looks outside its
        preference is a giveaway the model would exploit instead of learning.
        """
        score = (
            seg["discount_pull"] * (product.discount_pct / 70.0)
            + seg["price_pull"] * (math.log1p(product.price) / log_max_price)
            + seg["rating_pull"] * ((product.rating - 3.0) / 2.0)
        )
        if seg["brand_focus"] and product.brand in favourite_brands:
            score += 2.0
        return math.exp(score)

    n_users = max(50, count // 60)
    now = datetime.now(UTC)
    user_rows, pref_rows, inter_rows = [], [], []
    segment_names = list(SEGMENTS)
    segment_counts: dict[str, int] = dict.fromkeys(segment_names, 0)

    for _ in range(n_users):
        uid = new_id()
        segment_name = rng.choice(segment_names)
        seg = SEGMENTS[segment_name]
        segment_counts[segment_name] += 1
        affinity = rng.sample(categories, k=min(3, len(categories)))
        favourite_brands = (
            set(rng.sample(brands, k=min(seg["brand_focus"], len(brands))))
            if seg["brand_focus"] else set()
        )
        user_rows.append({
            "id": uid, "name": None, "email": None,
            "is_anonymous": True, "created_at": now - timedelta(days=rng.randint(1, 90)),
        })
        pref_rows.append({
            "id": new_id(), "user_id": uid,
            "preferred_categories": affinity,
            "preferred_brands": sorted(favourite_brands),
            "min_price": None, "max_price": None,
            "price_bias": {"deal_seeker": "value", "premium_buyer": "premium"}
                          .get(segment_name, "balanced"),
            "delivery_bias": rng.choice(["fast", "standard"]),
            "brand_affinity": {}, "category_affinity": {}, "subcategory_affinity": {},
            # The segment is recorded so the model has a label to train on. It
            # is ground truth for the synthetic data only; a real deployment
            # would have to infer it without one.
            "segment": segment_name,
            "updated_at": now,
        })

        n_events = max(1, int(rng.gauss(count / n_users * seg["view_rate"], 6)))
        for _ in range(n_events):
            # 75% of activity inside the user's affinity categories.
            cat = rng.choice(affinity) if rng.random() < 0.75 else rng.choice(categories)
            pool = by_category[cat]
            weights = [
                pop_weight[p.id] * segment_weight(p, seg, favourite_brands) for p in pool
            ]
            product = rng.choices(pool, weights=weights, k=1)[0]

            # Conversion is segment-dependent, and for a deal seeker it also
            # depends on the deal in front of them -- which is the entire
            # premise of sending that segment a coupon.
            itype_weights = dict(INTERACTION_WEIGHTS)
            purchase_pull = seg["purchase_rate"]
            if segment_name == "deal_seeker":
                purchase_pull *= 0.4 + 2.0 * (product.discount_pct / 70.0)
            itype_weights["purchased"] *= purchase_pull
            itype = rng.choices(
                list(itype_weights), weights=list(itype_weights.values()), k=1
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
