"""Offline ranking evaluation.

    python ml/evaluation/run_eval.py

Writes ml/evaluation/results/ranking_eval.json and .md. Both are committed so
the numbers quoted in README.md can be traced to the run that produced them.

Query set: every item in every knowledge-base goal (82 items across 5 goals).

TWO SETTINGS, BECAUSE THE PIPELINE HAS TWO STAGES
--------------------------------------------------
`candidates_for_requirement` filters to the item's subcategory in SQL and
orders what survives by TF-IDF; only then does the weighted scorer rank. Those
stages answer different questions, and evaluating them in one pool would
credit the wrong component.

  retrieval -- pool is every product in the item's *category*. Which shelf
    does the item live on? Relevance threshold 1: on the right shelf at all.

  ranking -- pool is every product in the item's *subcategory*, which is what
    the scorer actually receives in production. The shelf is already correct
    for everything, so relevance threshold is 2: has every required feature
    and is priced in band. At threshold 1 every ranker scores ~1.0 here,
    including random, which measures nothing.

Read relevance.py before quoting any number from this file. The ground truth
is derived from the requirement specification, not from users.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "ml"))

from app.db.database import SessionLocal
from app.kb.loader import load_kb
from app.models.product import Product
from app.services.product_search import get_search_service
from app.services.ranking import (
    COMPONENTS,
    RequirementSpec,
    ScoringContext,
    derive_context_tags,
    get_ranking_config,
)
from evaluation import baselines
from evaluation.metrics import (
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from evaluation.relevance import label_pool
from sqlalchemy import func, select

K_VALUES = (1, 3, 5, 10)
RESULTS_DIR = Path(__file__).parent / "results"

RANKERS = {
    "smartbuy": baselines.rank_smartbuy,
    "semantic_tfidf": baselines.rank_semantic,
    "popularity": baselines.rank_popularity,
    "rating": baselines.rank_rating,
    "price_asc": baselines.rank_price_asc,
    "random": baselines.rank_random,
}

SETTINGS = {
    "retrieval": {
        "pool": "category",
        "threshold": 1,
        "question": "Does the ranker surface products from the right shelf?",
    },
    "ranking": {
        "pool": "subcategory",
        "threshold": 2,
        "question": "Within the right shelf, does it surface products that meet "
        "every required feature and the price band?",
    },
}

# A pool with fewer products than this cannot separate rankers at k=10, so it
# is excluded and reported rather than averaged in as noise.
MIN_POOL = 12


def build_queries(db, pool_kind: str, threshold: int):
    """One evaluation query per knowledge-base item.

    Items whose pool holds no relevant product, or too few products to rank,
    are dropped and reported. They measure catalog coverage rather than
    ranking, and averaging a forced 0.0 into every ranker flatters the weak
    ones -- random scores the same 0.0 as the real scorer on an impossible
    query, which narrows the reported gap for free.
    """
    queries, skipped = [], []

    for goal in load_kb().values():
        ctx = ScoringContext(tags=derive_context_tags(goal.context_defaults))

        for item in goal.items:
            if pool_kind == "subcategory" and item.subcategory:
                where = Product.subcategory == item.subcategory
            elif item.category:
                where = Product.category == item.category
            else:
                skipped.append({"goal": goal.key, "item": item.key, "why": "no category"})
                continue

            pool = list(db.scalars(select(Product).where(where)))
            if len(pool) < MIN_POOL:
                skipped.append(
                    {
                        "goal": goal.key,
                        "item": item.key,
                        "why": f"pool too small ({len(pool)} products)",
                    }
                )
                continue

            gains = label_pool(pool, item)
            n_relevant = sum(1 for g in gains if g >= threshold)
            if n_relevant == 0:
                skipped.append(
                    {"goal": goal.key, "item": item.key, "why": "no relevant product in catalog"}
                )
                continue

            spec = RequirementSpec(
                item_name=item.item_name,
                category=item.category,
                subcategory=item.subcategory,
                required_features=item.required_features,
                preferred_features=item.preferred_features,
                est_price_min=item.est_price_min,
                est_price_max=item.est_price_max,
                search_terms=item.search_terms,
            )
            queries.append(
                {
                    "goal": goal.key,
                    "item": item.key,
                    "spec": spec,
                    "ctx": ctx,
                    "pool": pool,
                    "pool_size": len(pool),
                    # strict: a length mismatch here would silently attach the
                    # wrong label to every product after the divergence point.
                    "gains_by_id": {p.id: g for p, g in zip(pool, gains, strict=True)},
                    "ideal_gains": sorted(gains, reverse=True),
                    "n_relevant": n_relevant,
                }
            )

    return queries, skipped


def evaluate(rank_fn, queries, cfg, threshold: int, **kwargs) -> dict:
    per_k = {k: {"precision": [], "recall": [], "ndcg": []} for k in K_VALUES}
    rr = []

    for q in queries:
        ordered = rank_fn(q["pool"], spec=q["spec"], ctx=q["ctx"], cfg=cfg, **kwargs)
        gains = [q["gains_by_id"][p.id] for p in ordered]
        rr.append(reciprocal_rank(gains, threshold))
        for k in K_VALUES:
            per_k[k]["precision"].append(precision_at_k(gains, k, threshold))
            per_k[k]["recall"].append(recall_at_k(gains, k, q["n_relevant"], threshold))
            per_k[k]["ndcg"].append(ndcg_at_k(gains, k, q["ideal_gains"]))

    out = {"mrr": round(mean(rr), 4)}
    for k in K_VALUES:
        for metric, values in per_k[k].items():
            out[f"{metric}@{k}"] = round(mean(values), 4)
    return out


def ablate(queries, cfg, threshold: int) -> list[dict]:
    """Zero one component's weight at a time and renormalise the rest.

    This is the part of the evaluation the ground truth cannot flatter.
    `quality`, `review_strength`, `delivery` and `deal_value` are invisible to
    the relevance labels, so any NDCG they contribute is earned by correlating
    with genuine fitness rather than by restating the label. A component whose
    delta is negative is actively hurting and should be reweighted.
    """
    base = evaluate(baselines.rank_smartbuy, queries, cfg, threshold)["ndcg@10"]
    rows = []

    for dropped in COMPONENTS:
        weights = {c: w for c, w in cfg.weights.items() if c != dropped}
        total = sum(weights.values()) or 1.0
        weights = {c: w / total for c, w in weights.items()}
        score = evaluate(baselines.rank_smartbuy, queries, cfg, threshold, weights=weights)
        rows.append(
            {
                "component": dropped,
                "weight": round(cfg.weights[dropped], 4),
                "ndcg@10_without": round(score["ndcg@10"], 4),
                "delta": round(base - score["ndcg@10"], 4),
            }
        )

    rows.sort(key=lambda r: -r["delta"])
    return rows


def run_setting(db, name: str, spec: dict, cfg) -> dict:
    queries, skipped = build_queries(db, spec["pool"], spec["threshold"])
    if not queries:
        raise SystemExit(f"Setting {name!r} produced no evaluable queries -- is the catalog seeded?")

    pool_sizes = [q["pool_size"] for q in queries]
    print(f"\n[{name}] {len(queries)} queries, {len(skipped)} skipped, "
          f"pool {min(pool_sizes)}-{max(pool_sizes)} products")

    rankers = {}
    for ranker_name, fn in RANKERS.items():
        rankers[ranker_name] = evaluate(fn, queries, cfg, spec["threshold"])
        print(f"  {ranker_name:16} NDCG@10={rankers[ranker_name]['ndcg@10']:.4f}")

    print("  running ablation...")
    return {
        "question": spec["question"],
        "pool": spec["pool"],
        "relevance_threshold": spec["threshold"],
        "n_queries": len(queries),
        "n_skipped": len(skipped),
        "pool_size_min": min(pool_sizes),
        "pool_size_max": max(pool_sizes),
        "pool_size_mean": round(mean([float(s) for s in pool_sizes]), 1),
        "rankers": rankers,
        "ablation": ablate(queries, cfg, spec["threshold"]),
        "skipped": skipped,
    }


def _ranker_table(rankers: dict) -> list[str]:
    lines = [
        "| Ranker | P@1 | P@5 | P@10 | R@10 | NDCG@5 | NDCG@10 | MRR |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in rankers.items():
        lines.append(
            f"| `{name}` | {m['precision@1']:.3f} | {m['precision@5']:.3f} | "
            f"{m['precision@10']:.3f} | {m['recall@10']:.3f} | {m['ndcg@5']:.3f} | "
            f"{m['ndcg@10']:.3f} | {m['mrr']:.3f} |"
        )
    return lines


def to_markdown(report: dict) -> str:
    lines = [
        "# Ranking evaluation",
        "",
        "<!-- Generated by ml/evaluation/run_eval.py. Do not edit by hand. -->",
        "",
        f"Generated: `{report['generated_at']}`  ",
        f"Catalog: {report['catalog_size']} products  ",
        f"Query set: {report['n_kb_items']} knowledge-base items across "
        f"{report['n_goals']} goals",
        "",
        "Relevance is derived from the requirement specification, not from user",
        "behaviour -- there is no click or purchase data behind these numbers, and",
        "none of them should be read as a measure of user satisfaction.",
        "`ml/evaluation/relevance.py` states the labelling rule and its limits in",
        "full. Read it before quoting anything here.",
        "",
    ]

    for name, setting in report["settings"].items():
        lines += [
            f"## Setting: {name}",
            "",
            f"{setting['question']}",
            "",
            f"Pool: every product in the item's {setting['pool']} "
            f"({setting['pool_size_min']}-{setting['pool_size_max']} products, "
            f"mean {setting['pool_size_mean']}).  ",
            f"Relevance threshold: gain >= {setting['relevance_threshold']}.  ",
            f"Queries: {setting['n_queries']} ({setting['n_skipped']} skipped).",
            "",
            *_ranker_table(setting["rankers"]),
            "",
            "### Ablation: NDCG@10 with one component removed",
            "",
            "Each row drops one scoring component and renormalises the remaining",
            "weights. A positive delta means the component was helping.",
            "",
            "| Component | Weight | NDCG@10 without | Delta |",
            "| --- | --- | --- | --- |",
        ]
        for row in setting["ablation"]:
            lines.append(
                f"| `{row['component']}` | {row['weight']:.3f} | "
                f"{row['ndcg@10_without']:.4f} | {row['delta']:+.4f} |"
            )
        lines.append("")

    lines += [
        "## Skipped queries",
        "",
        "Coverage gaps, not ranking failures. Listed so the query count above is",
        "auditable.",
        "",
    ]
    for name, setting in report["settings"].items():
        if not setting["skipped"]:
            continue
        lines.append(f"**{name}**")
        lines.append("")
        for s in setting["skipped"]:
            lines.append(f"- `{s['goal']}/{s['item']}` -- {s['why']}")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    db = SessionLocal()
    try:
        get_search_service().warm(db)
        cfg = get_ranking_config()
        kb = load_kb()

        report = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "catalog_size": db.scalar(select(func.count(Product.id))),
            "n_goals": len(kb),
            "n_kb_items": sum(len(g.items) for g in kb.values()),
            "k_values": list(K_VALUES),
            "weights": cfg.weights,
            "settings": {},
        }

        for name, spec in SETTINGS.items():
            report["settings"][name] = run_setting(db, name, spec, cfg)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        (RESULTS_DIR / "ranking_eval.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        (RESULTS_DIR / "ranking_eval.md").write_text(to_markdown(report), encoding="utf-8")
        print(f"\nWrote {RESULTS_DIR / 'ranking_eval.json'} and .md")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
