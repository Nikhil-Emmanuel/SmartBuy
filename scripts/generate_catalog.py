"""Generate the curated multi-marketplace product catalog.

    python scripts/generate_catalog.py [--seed 42] [--out data/products/catalog.json]

Deterministic by design: the same seed produces byte-identical output, so the
demo is reproducible and a regenerated catalog never invalidates a rehearsed
run. Standard library only -- this runs without the backend venv.

Owner: Member 2 (Data Engineering).

HONESTY: every row is simulated data with simulated pricing, flagged
is_simulated=True and badged in the UI. Brands are fictional. We do not claim
real-time marketplace prices anywhere in this project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog_archetypes import (  # noqa: E402
    ALL_ARCHETYPES,
    BRANDS,
    DOMAIN_BRAND_POOL,
    MARKETPLACES,
    TIER_MULTIPLIER,
)

ROOT = Path(__file__).resolve().parents[1]

MODEL_TOKENS = [
    "", "", "", "Pro", "Lite", "Plus", "Max", "Elite", "Core", "Prime",
    "II", "III", "X", "Ultra", "Essential", "Classic", "Trail", "Summit",
]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def group_key(brand: str, subcategory: str, model: str) -> str:
    raw = f"{brand}|{subcategory}|{model}".lower()
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def round_price(value: float) -> int:
    """Round to a retail-looking integer: ...99 below 5k, ...999 above."""
    v = int(value)
    if v < 500:
        return max(99, (v // 10) * 10 + 9)
    if v < 5000:
        return (v // 100) * 100 + 99
    return (v // 1000) * 1000 + 999


def build_description(
    rng: random.Random, name: str, arch: dict, features: list[str], specs: dict
) -> str:
    """Feature-rich prose. This is the text TF-IDF retrieval actually reads,
    so it must contain the words a requirement would search for."""
    feature_phrases = {
        "waterproof": "fully waterproof construction",
        "water_resistant": "water-resistant finish",
        "windproof": "windproof outer shell",
        "insulated": "insulated for cold conditions",
        "thermal": "thermal heat retention",
        "breathable": "breathable fabric",
        "lightweight": "lightweight build",
        "quick_dry": "quick-drying material",
        "anti_slip": "anti-slip grip",
        "adjustable": "adjustable fit",
        "foldable": "folds down compactly",
        "rechargeable": "USB rechargeable",
        "shock_absorbing": "shock-absorbing support",
        "uv_protection": "UV protection",
        "machine_washable": "machine washable",
        "compact": "compact form factor",
        "durable": "built for durability",
        "ergonomic": "ergonomic design",
        "leak_proof": "leak-proof seal",
        "insulating": "temperature insulating",
        "high_grip": "high-grip surface",
        "reflective": "reflective detailing",
        "seam_sealed": "seam-sealed for weather protection",
        "moisture_wicking": "moisture-wicking",
        "anti_bacterial": "anti-bacterial treatment",
        "portable": "easy to carry",
        "energy_efficient": "energy efficient",
        "warranty_included": "manufacturer warranty included",
    }
    parts = [f"{name} designed for {', '.join(arch['tags'][:3]).replace('_', ' ')} use."]

    chosen = [feature_phrases.get(f, f.replace("_", " ")) for f in features[:5]]
    if chosen:
        parts.append("Features " + ", ".join(chosen) + ".")

    if specs:
        spec_bits = [f"{k.replace('_', ' ')}: {v}" for k, v in list(specs.items())[:3]]
        parts.append("Specifications - " + "; ".join(spec_bits) + ".")

    parts.append(
        rng.choice([
            "Suitable for beginners and regular users alike.",
            "A dependable everyday choice.",
            "Tested for regular outdoor and travel use.",
            "Popular pick for first-time buyers.",
            "Balanced option across price and performance.",
        ])
    )
    return " ".join(parts)


def make_specs(rng: random.Random, arch: dict) -> dict:
    return {k: rng.choice(v) for k, v in arch.get("specs", {}).items()}


def generate(seed: int, scale: float = 1.0) -> dict:
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)

    products: list[dict] = []
    offers: list[dict] = []
    seen_external: set[tuple[str, str]] = set()

    for arch in ALL_ARCHETYPES:
        pool = BRANDS[DOMAIN_BRAND_POOL[arch["domain"]]]
        lo, hi = arch["price_range"]

        # Floor of 10 models per archetype: a requirement that resolves to
        # three candidates makes the comparison table look broken on stage.
        n_models = max(10, round(arch["models"] * scale))

        for i in range(n_models):
            brand, tier, quality_bias = rng.choice(pool)
            title = rng.choice(arch["titles"])
            token = rng.choice(MODEL_TOKENS)
            model_num = rng.choice(["", "", str(rng.randrange(100, 999, 50))])
            model = " ".join(t for t in (title, token, model_num) if t).strip()
            name = f"{brand} {model}"

            # --- price band from archetype range, shifted by brand tier ---
            tlo, thi = TIER_MULTIPLIER[tier]
            position = rng.random()
            base = lo + (hi - lo) * position
            mrp_float = base * rng.uniform(tlo, thi)
            mrp_float = max(lo * 0.7, min(hi * 1.4, mrp_float))

            features = list(arch["required_features"])
            n_opt = rng.randint(2, min(5, len(arch["optional_features"])))
            features += rng.sample(arch["optional_features"], n_opt)
            features = sorted(set(features))

            specs = make_specs(rng, arch)

            # --- quality signals ---
            # Price position within the archetype correlates with rating, but
            # loosely: expensive is not automatically better, which is what
            # makes "best budget" a genuinely different answer to "best rated".
            rating = 3.55 + quality_bias + position * 0.55 + rng.uniform(-0.45, 0.45)
            rating = round(max(3.0, min(4.9, rating)), 1)

            # Budget items accumulate more reviews (they sell more units).
            volume_bias = 1.6 - position
            review_count = int(math.exp(rng.uniform(3.2, 8.4)) * volume_bias)
            review_count = max(11, min(48000, review_count))

            tags = list(arch["tags"])
            tags.append({"budget": "value", "mid": "mid_range", "premium": "premium"}[tier])
            if rating >= 4.3:
                tags.append("highly_rated")

            gkey = group_key(brand, arch["subcategory"], model)

            # --- list on 1-3 marketplaces ---
            names = list(MARKETPLACES)
            weights = [MARKETPLACES[m]["listing_weight"] for m in names]
            primary = rng.choices(names, weights=weights, k=1)[0]
            listings = [primary]
            # ~38% of groups appear on a second source, ~12% on all three.
            # Cross-listing is what makes the comparison table meaningful.
            roll = rng.random()
            if roll < 0.38:
                others = [m for m in names if m != primary]
                listings.append(rng.choice(others))
                if roll < 0.12:
                    listings = names[:]

            for source in listings:
                mkt = MARKETPLACES[source]
                mrp = round_price(mrp_float * rng.uniform(*mkt["price_factor"]))

                discount_pct = 0
                if rng.random() < 0.72:
                    discount_pct = rng.randint(5, 42) + mkt["discount_bonus"]
                    discount_pct = min(discount_pct, 55)
                price = round_price(mrp * (1 - discount_pct / 100))
                price = min(price, mrp)
                # Recompute so the displayed % always matches the two numbers.
                discount_pct = round(100 * (mrp - price) / mrp) if mrp else 0

                dlo, dhi = mkt["delivery"]
                delivery_days = rng.randint(dlo, dhi)

                avail = rng.choices(
                    ["in_stock", "low_stock", "out_of_stock"],
                    weights=[0.87, 0.09, 0.04],
                    k=1,
                )[0]

                ext_id = f"{source[-1]}-{slugify(arch['key'])}-{i:03d}-{gkey[:6]}"
                if (source, ext_id) in seen_external:
                    continue
                seen_external.add((source, ext_id))

                pid = hashlib.md5(f"{source}|{ext_id}".encode()).hexdigest()
                pid = f"{pid[:8]}-{pid[8:12]}-{pid[12:16]}-{pid[16:20]}-{pid[20:32]}"

                products.append({
                    "id": pid,
                    "source": source,
                    "external_product_id": ext_id,
                    "name": name,
                    "brand": brand,
                    "category": arch["category"],
                    "subcategory": arch["subcategory"],
                    "description": build_description(rng, name, arch, features, specs),
                    "price": price,
                    "original_price": mrp,
                    "discount_pct": discount_pct,
                    "rating": rating,
                    "review_count": review_count,
                    "features": features,
                    "specs": specs,
                    "tags": sorted(set(tags)),
                    "availability": avail,
                    "delivery_days": delivery_days,
                    "url": f"https://example-{source.lower().replace('_', '-')}.test/p/{ext_id}",
                    "image_url": "",  # frontend renders a deterministic placeholder
                    "product_group_key": gkey,
                    "is_simulated": True,
                })

                # --- offers on ~28% of listings ---
                if rng.random() < 0.28:
                    otype = rng.choices(
                        ["coupon", "bank_offer", "discount", "bundle"],
                        weights=[0.35, 0.3, 0.2, 0.15], k=1,
                    )[0]
                    flat = 0
                    extra_pct = 0
                    if otype in ("coupon", "discount"):
                        extra_pct = rng.choice([5, 7, 10, 12, 15])
                        desc = f"Extra {extra_pct}% off at checkout"
                    elif otype == "bank_offer":
                        flat = rng.choice([100, 150, 250, 500, 750])
                        desc = f"Rs {flat} instant discount on select bank cards"
                    else:
                        flat = rng.choice([200, 300, 500])
                        desc = f"Save Rs {flat} when bought with a related item"

                    offers.append({
                        "product_id": pid,
                        "offer_type": otype,
                        "discount_pct": extra_pct,
                        "flat_discount": flat,
                        "coupon_code": (
                            f"SB{rng.randrange(100, 999)}" if otype == "coupon" else None
                        ),
                        "description": desc,
                        "valid_from": (now - timedelta(days=rng.randint(1, 20))).isoformat(),
                        "valid_to": (now + timedelta(days=rng.randint(5, 60))).isoformat(),
                    })

    return {
        "generated_at": now.isoformat(),
        "seed": seed,
        "scale": scale,
        "disclaimer": (
            "Simulated catalog. Fictional brands, simulated pricing, no real-time data. "
            "Every product is flagged is_simulated=true."
        ),
        "count": len(products),
        "offer_count": len(offers),
        "products": products,
        "offers": offers,
    }


def summarize(payload: dict) -> None:
    products = payload["products"]
    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    groups: dict[str, set] = {}
    for p in products:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
        by_category[p["category"]] = by_category.get(p["category"], 0) + 1
        groups.setdefault(p["product_group_key"], set()).add(p["source"])

    multi = sum(1 for s in groups.values() if len(s) > 1)
    in_stock = sum(1 for p in products if p["availability"] == "in_stock")

    print(f"  products         {len(products)}")
    print(f"  offers           {payload['offer_count']}")
    print(f"  product groups   {len(groups)}  ({multi} cross-listed = "
          f"{100 * multi / max(1, len(groups)):.0f}%)")
    print(f"  in stock         {100 * in_stock / max(1, len(products)):.0f}%")
    print(f"  by source        {dict(sorted(by_source.items()))}")
    print("  by category      " + ", ".join(
        f"{k}:{v}" for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])))
    prices = [p["price"] for p in products]
    print(f"  price range      Rs {min(prices):,} - Rs {max(prices):,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--scale", type=float, default=2.6,
                    help="Models per archetype multiplier. 2.6 -> ~3,000 SKUs.")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "products" / "catalog.json")
    args = ap.parse_args()

    payload = generate(args.seed, args.scale)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, ensure_ascii=True), encoding="utf-8")

    size_mb = args.out.stat().st_size / 1_048_576
    print(f"Catalog written to {args.out}  ({size_mb:.1f} MB)")
    summarize(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
