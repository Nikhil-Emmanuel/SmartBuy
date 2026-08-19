"""Product discovery: SQL filtering + TF-IDF semantic retrieval.

ADR-003: TF-IDF + cosine rather than FAISS. At ~3k SKUs the retrieval quality
difference is not observable and it removes a native-dependency risk. The
SemanticIndex interface is what FAISS would slot into later.

Owner: Member 3 (ML) with Member 6 (Backend).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import SOURCE_DISPLAY_NAMES, Availability
from app.models.product import Product
from app.services.ranking import RequirementSpec, get_ranking_config

log = logging.getLogger("smartbuy.search")


def product_text(p: Product) -> str:
    """The document TF-IDF actually indexes.

    Brand, subcategory and tags are repeated because a query like 'waterproof
    trekking jacket' should match on category words as strongly as on prose.
    """
    parts = [
        p.name, p.name,
        p.brand,
        p.category.replace("_", " "),
        p.subcategory.replace("_", " "), p.subcategory.replace("_", " "),
        " ".join(f.replace("_", " ") for f in (p.features or [])),
        " ".join(t.replace("_", " ") for t in (p.tags or [])),
        p.description or "",
    ]
    return " ".join(parts).lower()


class SemanticIndex:
    """In-memory TF-IDF index. Thread-safe build, lock-free query."""

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._ids: list[str] = []
        self._pos: dict[str, int] = {}
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._ids)

    @property
    def is_built(self) -> bool:
        return self._matrix is not None

    def build(self, products: list[Product]) -> int:
        with self._lock:
            if not products:
                log.warning("Semantic index build skipped: no products")
                return 0
            texts = [product_text(p) for p in products]
            vectorizer = TfidfVectorizer(
                lowercase=True,
                stop_words="english",
                ngram_range=(1, 2),
                min_df=1,
                max_df=0.85,
                sublinear_tf=True,
            )
            matrix = vectorizer.fit_transform(texts)
            self._vectorizer = vectorizer
            self._matrix = matrix
            self._ids = [p.id for p in products]
            self._pos = {pid: i for i, pid in enumerate(self._ids)}
            log.info("Semantic index built: %d docs, %d terms",
                     matrix.shape[0], matrix.shape[1])
            return len(self._ids)

    def query(
        self,
        text: str,
        top_k: int = 50,
        allowed_ids: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Return (product_id, similarity) sorted descending."""
        if not self.is_built or not text.strip():
            return []

        vec = self._vectorizer.transform([text.lower()])
        sims = linear_kernel(vec, self._matrix).ravel()

        if allowed_ids is not None:
            if not allowed_ids:
                return []
            mask = np.zeros(len(sims), dtype=bool)
            for pid in allowed_ids:
                idx = self._pos.get(pid)
                if idx is not None:
                    mask[idx] = True
            sims = np.where(mask, sims, -1.0)

        k = min(top_k, len(sims))
        if k <= 0:
            return []
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [(self._ids[i], float(sims[i])) for i in top if sims[i] > 0.0]


@dataclass
class SearchFilters:
    q: str | None = None
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_rating: float | None = None
    source: str | None = None
    # Multi-select marketplace filter. None means "no opinion, use everything";
    # an empty list is a user who switched every marketplace off, and must stay
    # distinct from None or we would silently show them what they excluded.
    sources: list[str] | None = None
    features: list[str] | None = None
    exclude_out_of_stock: bool = False


SORT_KEYS = {
    "price_asc": lambda p: p.price,
    "price_desc": lambda p: -p.price,
    "rating": lambda p: (-p.rating, -p.review_count),
    "delivery": lambda p: p.delivery_days,
    "deal": lambda p: -p.discount_pct,
    "reviews": lambda p: -p.review_count,
}

PRICE_BUCKETS: list[tuple[str, int, int]] = [
    ("Under Rs 500", 0, 499),
    ("Rs 500 - 1,500", 500, 1499),
    ("Rs 1,500 - 3,000", 1500, 2999),
    ("Rs 3,000 - 7,500", 3000, 7499),
    ("Rs 7,500 - 20,000", 7500, 19999),
    ("Above Rs 20,000", 20000, 10**9),
]


class ProductSearchService:
    def __init__(self) -> None:
        self.index = SemanticIndex()

    # -- index lifecycle ---------------------------------------------------
    def warm(self, db: Session) -> int:
        products = list(db.scalars(select(Product)))
        return self.index.build(products)

    def ensure_index(self, db: Session) -> None:
        if not self.index.is_built:
            self.warm(db)

    # -- filtering ---------------------------------------------------------
    def _filtered(self, db: Session, f: SearchFilters) -> list[Product]:
        stmt = select(Product)
        if f.category:
            stmt = stmt.where(Product.category == f.category)
        if f.subcategory:
            stmt = stmt.where(Product.subcategory == f.subcategory)
        if f.brand:
            stmt = stmt.where(Product.brand == f.brand)
        if f.source:
            stmt = stmt.where(Product.source == f.source)
        if f.sources is not None:
            stmt = stmt.where(Product.source.in_(f.sources))
        if f.min_price is not None:
            stmt = stmt.where(Product.price >= f.min_price)
        if f.max_price is not None:
            stmt = stmt.where(Product.price <= f.max_price)
        if f.min_rating is not None:
            stmt = stmt.where(Product.rating >= f.min_rating)
        if f.exclude_out_of_stock:
            stmt = stmt.where(Product.availability != Availability.OUT_OF_STOCK)

        rows = list(db.scalars(stmt))

        # features live in a JSON column; filtering them portably means Python.
        if f.features:
            wanted = {x.lower() for x in f.features}
            rows = [p for p in rows if wanted <= {x.lower() for x in (p.features or [])}]
        return rows

    # -- public search -----------------------------------------------------
    def search(
        self,
        db: Session,
        filters: SearchFilters,
        sort: str = "relevance",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int, dict]:
        self.ensure_index(db)
        rows = self._filtered(db, filters)

        if filters.q and filters.q.strip():
            allowed = {p.id for p in rows}
            ranked = self.index.query(filters.q, top_k=max(200, page * page_size), allowed_ids=allowed)
            order = {pid: i for i, (pid, _) in enumerate(ranked)}
            matched = [p for p in rows if p.id in order]
            if matched:
                matched.sort(key=lambda p: order[p.id])
                rows = matched
            # If TF-IDF matched nothing, fall through with the SQL-filtered set
            # rather than showing an empty page for a valid query.

        if sort in SORT_KEYS:
            rows.sort(key=SORT_KEYS[sort])
        elif sort == "relevance" and not (filters.q or "").strip():
            rows.sort(key=lambda p: (-p.rating * min(1.0, p.review_count / 500), -p.review_count))

        total = len(rows)
        facets = self._facets(rows)
        start = max(0, (page - 1) * page_size)
        return rows[start : start + page_size], total, facets

    def _facets(self, rows: list[Product]) -> dict:
        brands: dict[str, int] = {}
        sources: dict[str, int] = {}
        categories: dict[str, int] = {}
        buckets = {label: 0 for label, _, _ in PRICE_BUCKETS}

        for p in rows:
            brands[p.brand] = brands.get(p.brand, 0) + 1
            name = SOURCE_DISPLAY_NAMES.get(p.source, p.source)
            sources[name] = sources.get(name, 0) + 1
            categories[p.category] = categories.get(p.category, 0) + 1
            for label, lo, hi in PRICE_BUCKETS:
                if lo <= p.price <= hi:
                    buckets[label] += 1
                    break

        top_brands = dict(sorted(brands.items(), key=lambda kv: -kv[1])[:15])
        return {
            "brands": top_brands,
            "sources": sources,
            "categories": categories,
            "price_buckets": [
                {"label": label, "min_price": lo, "max_price": hi, "count": buckets[label]}
                for label, lo, hi in PRICE_BUCKETS
                if buckets[label] > 0
            ],
        }

    def infer_taxonomy(self, db: Session, query: str,
                       top_k: int = 15) -> tuple[str, str]:
        """Best-guess (category, subcategory) for a free-text product query.

        Mode A has no knowledge-base entry to tell it what shelf to look on,
        so it asks the index: whichever subcategory dominates the strongest
        matches is the shelf. Without this, "waterproof trekking shoes"
        happily returns waterproof trekking gaiters -- every word matches,
        and it is still the wrong product.
        """
        self.ensure_index(db)
        ranked = self.index.query(query, top_k=top_k)
        if not ranked:
            return "", ""

        weights = dict(ranked)
        rows = db.execute(
            select(Product.id, Product.category, Product.subcategory)
            .where(Product.id.in_(list(weights)))
        ).all()

        scores: dict[tuple[str, str], float] = {}
        for pid, category, subcategory in rows:
            key = (category, subcategory)
            scores[key] = scores.get(key, 0.0) + weights.get(pid, 0.0)

        if not scores:
            return "", ""
        best, best_score = max(scores.items(), key=lambda kv: kv[1])
        total = sum(scores.values())
        # A clear winner only. A flat distribution means the query is broad
        # ("camping gear"), and narrowing it would hide good products.
        if total <= 0 or best_score / total < 0.34:
            return best[0], ""
        return best

    # -- requirement-driven candidate retrieval ----------------------------
    def candidates_for_requirement(
        self,
        db: Session,
        req: RequirementSpec,
        limit: int = 40,
        budget_ceiling: int | None = None,
        sources: list[str] | None = None,
    ) -> list[Product]:
        """Candidate set for one requirement, before scoring.

        Hard filters are applied here so the scorer never has to reject
        anything: what comes back is genuinely purchasable for this need.
        """
        self.ensure_index(db)
        cfg = get_ranking_config()

        base = SearchFilters(
            subcategory=req.subcategory or None,
            min_rating=float(cfg.filters.get("min_rating", 0.0)) or None,
            sources=sources,
        )
        rows = self._filtered(db, base)

        # Fall back to the broader category, then to pure semantic search, so a
        # KB item whose subcategory has thin coverage still returns something.
        # The marketplace filter rides along every fallback: a widening search
        # must not quietly reintroduce a marketplace the user switched off.
        if len(rows) < 6 and req.category:
            rows = self._filtered(db, SearchFilters(category=req.category, sources=sources))
        if len(rows) < 6:
            query = " ".join(req.search_terms or [req.item_name])
            ranked = self.index.query(query, top_k=limit * 2)
            ids = [pid for pid, _ in ranked]
            if ids:
                stmt = select(Product).where(Product.id.in_(ids))
                if sources is not None:
                    stmt = stmt.where(Product.source.in_(sources))
                rows = list(db.scalars(stmt))

        if not rows:
            return []

        # Price ceiling: the item's own estimate, tightened by the remaining
        # budget when one is supplied.
        overshoot = 1.0 if req.hard_price_cap else float(
            cfg.filters.get("max_price_overshoot", 1.35))
        ceiling = int(req.est_price_max * overshoot) if req.est_price_max else None
        if budget_ceiling:
            ceiling = min(ceiling, budget_ceiling) if ceiling else budget_ceiling
        if ceiling:
            affordable = [p for p in rows if p.price <= ceiling]
            if req.hard_price_cap:
                # The user named this figure. Showing them a Rs 3,400 product
                # after they said "under Rs 3,000" is not a helpful suggestion.
                rows = affordable
            else:
                # Never return an empty set purely on an estimated band -- the
                # caller needs candidates to explain that everything is over.
                rows = affordable or sorted(rows, key=lambda p: p.price)[:limit]

        query = " ".join(req.search_terms or [req.item_name])
        if query.strip():
            allowed = {p.id for p in rows}
            ranked = self.index.query(query, top_k=limit, allowed_ids=allowed)
            order = {pid: i for i, (pid, _) in enumerate(ranked)}
            if order:
                rows.sort(key=lambda p: order.get(p.id, 10**6))

        return rows[:limit]


_service: ProductSearchService | None = None


def get_search_service() -> ProductSearchService:
    global _service
    if _service is None:
        _service = ProductSearchService()
    return _service
