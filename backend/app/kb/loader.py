"""Requirement knowledge base loader.

Loads every YAML goal from app/kb/goals, resolves `extends` inheritance and
exposes goal lookup by key or by free text.

ADR-002: the KB is authoritative for requirements. A pure-LLM checklist is
non-reproducible across demo runs and can invent items with zero catalog
coverage, producing empty product sections on stage.

The ADR permitted the LLM to augment the list but never to replace it. In
practice the augmentation path was never implemented, so what ships is the
stricter version: this loader is the only source of requirements.

Owner: Member 4 (Requirements/Optimization).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import settings
from app.core.constants import CATEGORIES, FEATURES, Priority

log = logging.getLogger("smartbuy.kb")

MAX_EXTENDS_DEPTH = 5


@dataclass
class KBItem:
    key: str
    item_name: str
    category: str
    subcategory: str = ""
    priority: str = Priority.ESSENTIAL
    quantity_rule: str | int = 1
    conditions: list[str] = field(default_factory=list)
    promote_to_essential_when: list[str] = field(default_factory=list)
    reason: str = ""
    search_terms: list[str] = field(default_factory=list)
    required_features: list[str] = field(default_factory=list)
    preferred_features: list[str] = field(default_factory=list)
    est_price_range: tuple[int, int] = (0, 0)

    @property
    def est_price_min(self) -> int:
        return int(self.est_price_range[0])

    @property
    def est_price_max(self) -> int:
        return int(self.est_price_range[1])


@dataclass
class KBGoal:
    key: str
    display_name: str
    domain: str
    aliases: list[str] = field(default_factory=list)
    context_defaults: dict = field(default_factory=dict)
    items: list[KBItem] = field(default_factory=list)

    def item(self, key: str) -> KBItem | None:
        return next((i for i in self.items if i.key == key), None)


def _merge_item(parent: dict, child: dict) -> dict:
    """Child overrides parent field-by-field. Anything the child does not
    restate keeps the parent's value."""
    merged = dict(parent)
    for k, v in child.items():
        if v is not None:
            merged[k] = v
    return merged


def _to_item(raw: dict) -> KBItem:
    price = raw.get("est_price_range") or [0, 0]
    return KBItem(
        key=raw["key"],
        item_name=raw.get("item_name", raw["key"].replace("_", " ").title()),
        category=raw.get("category", ""),
        subcategory=raw.get("subcategory", ""),
        priority=raw.get("priority", Priority.ESSENTIAL),
        quantity_rule=raw.get("quantity_rule", 1),
        conditions=list(raw.get("conditions") or []),
        promote_to_essential_when=list(raw.get("promote_to_essential_when") or []),
        reason=raw.get("reason", ""),
        search_terms=list(raw.get("search_terms") or []),
        required_features=list(raw.get("required_features") or []),
        preferred_features=list(raw.get("preferred_features") or []),
        est_price_range=(int(price[0]), int(price[1])),
    )


def _load_raw(goals_dir: Path) -> dict[str, dict]:
    raw: dict[str, dict] = {}
    for path in sorted(goals_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            log.exception("Skipping malformed KB file: %s", path.name)
            continue
        if not data or "key" not in data:
            log.warning("Skipping KB file without a key: %s", path.name)
            continue
        raw[data["key"]] = data
    return raw


def _resolve(key: str, raw: dict[str, dict], depth: int = 0) -> dict:
    """Flatten an `extends` chain into a single goal definition."""
    if depth > MAX_EXTENDS_DEPTH:
        raise ValueError(f"KB inheritance too deep (cycle?) at {key!r}")

    data = raw[key]
    parent_key = data.get("extends")
    if not parent_key:
        return data
    if parent_key not in raw:
        log.error("KB goal %r extends unknown goal %r -- ignoring", key, parent_key)
        return data

    parent = _resolve(parent_key, raw, depth + 1)

    by_key: dict[str, dict] = {i["key"]: dict(i) for i in parent.get("items", [])}
    order: list[str] = [i["key"] for i in parent.get("items", [])]
    for child_item in data.get("items", []):
        ckey = child_item["key"]
        if ckey in by_key:
            by_key[ckey] = _merge_item(by_key[ckey], child_item)
        else:
            by_key[ckey] = dict(child_item)
            order.append(ckey)

    merged = dict(parent)
    merged.update({k: v for k, v in data.items() if k not in ("items", "extends")})
    merged["items"] = [by_key[k] for k in order]
    merged["context_defaults"] = {
        **(parent.get("context_defaults") or {}),
        **(data.get("context_defaults") or {}),
    }
    return merged


def _validate(goal: KBGoal) -> list[str]:
    """Vocabulary drift between the KB and the catalog is the single most
    likely way this project fails on stage: requirements silently match zero
    products. Surface it loudly at load time."""
    problems: list[str] = []
    valid_priorities = {p.value for p in Priority}
    for item in goal.items:
        if item.category and item.category not in CATEGORIES:
            problems.append(f"{goal.key}/{item.key}: unknown category {item.category!r}")
        if item.priority not in valid_priorities:
            problems.append(f"{goal.key}/{item.key}: unknown priority {item.priority!r}")
        for feat in item.required_features + item.preferred_features:
            if feat not in FEATURES:
                problems.append(f"{goal.key}/{item.key}: unknown feature {feat!r}")
    return problems


@lru_cache(maxsize=1)
def load_kb() -> dict[str, KBGoal]:
    goals_dir = Path(settings.KB_GOALS_DIR)
    if not goals_dir.exists():
        log.error("KB directory missing: %s", goals_dir)
        return {}

    raw = _load_raw(goals_dir)
    goals: dict[str, KBGoal] = {}
    all_problems: list[str] = []

    for key in raw:
        try:
            data = _resolve(key, raw)
        except ValueError:
            log.exception("Could not resolve KB goal %r", key)
            continue
        goal = KBGoal(
            key=data["key"],
            display_name=data.get("display_name", key.replace("_", " ").title()),
            domain=data.get("domain", "general"),
            aliases=list(data.get("aliases") or []),
            context_defaults=dict(data.get("context_defaults") or {}),
            items=[_to_item(i) for i in data.get("items", [])],
        )
        all_problems.extend(_validate(goal))
        goals[goal.key] = goal

    for problem in all_problems:
        log.error("KB validation: %s", problem)

    log.info("Knowledge base loaded: %d goals, %d items",
             len(goals), sum(len(g.items) for g in goals.values()))
    return goals


def get_goal(key: str | None) -> KBGoal | None:
    if not key:
        return None
    return load_kb().get(key)


def list_goals() -> list[KBGoal]:
    return list(load_kb().values())


def resolve_goal_from_text(text: str) -> KBGoal | None:
    """Match free text to a goal by key or alias.

    Longest alias wins, so 'winter trek' resolves to winter_trek rather than
    trek. This is the deterministic fallback used when the LLM is unavailable;
    when it is available the LLM supplies `activity` directly.
    """
    if not text:
        return None
    lowered = text.lower()

    candidates: list[tuple[int, KBGoal]] = []
    for goal in load_kb().values():
        needles = [goal.key.replace("_", " "), goal.display_name.lower(), *goal.aliases]
        for needle in needles:
            n = needle.lower().strip()
            if n and n in lowered:
                candidates.append((len(n), goal))

    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0])[1]
