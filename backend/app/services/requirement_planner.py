"""Requirement planning engine: goal + context -> structured requirement list.

Rules first, LLM second (ADR-002). Conditions and quantities come from the
knowledge base and are evaluated by the restricted DSL; the LLM may only add
items on top, and only when ENABLE_LLM_REQUIREMENT_AUGMENT is on.

Owner: Member 4 (Requirements/Optimization).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.core.constants import PRIORITY_ORDER, FulfillmentStatus, Priority
from app.kb.condition_dsl import evaluate_condition, evaluate_quantity
from app.kb.loader import KBGoal, KBItem, get_goal, resolve_goal_from_text
from app.services.context_inference import Assumption, infer_context

log = logging.getLogger("smartbuy.planner")

OWNERSHIP_MATCH_THRESHOLD = 80

# Domain filler words. "Trekking shoes" and "trekking socks" share the word
# that matters least; matching on it told users they already owned socks,
# poles and a dry bag when they had only mentioned shoes. Stripping these
# leaves the distinguishing noun, which is what ownership actually hinges on.
GENERIC_TOKENS = frozenset({
    "trekking", "trek", "hiking", "hike", "camping", "camp", "climbing",
    "winter", "summer", "monsoon", "snow", "cold", "weather", "season",
    "outdoor", "mountain", "travel", "adventure", "sports", "gear",
    "thermal", "insulated", "waterproof", "windproof", "lightweight",
    "portable", "compact", "quick", "dry", "anti", "shock", "uv",
    "set", "kit", "pair", "combo", "piece", "pack", "of", "with",
    "a", "an", "the", "my", "some", "for", "and", "already", "have", "own",
    "i", "we", "got", "new", "old", "good",
})


@dataclass
class PlannedRequirement:
    kb_item_key: str
    item_name: str
    category: str
    subcategory: str
    priority: str
    quantity: int
    reason: str
    est_price_min: int
    est_price_max: int
    search_terms: list[str] = field(default_factory=list)
    required_features: list[str] = field(default_factory=list)
    preferred_features: list[str] = field(default_factory=list)
    is_owned: bool = False
    owned_matched_from: str | None = None

    @property
    def fulfillment_status(self) -> str:
        return FulfillmentStatus.OWNED if self.is_owned else FulfillmentStatus.PENDING

    @property
    def est_total_min(self) -> int:
        return 0 if self.is_owned else self.est_price_min * self.quantity

    @property
    def est_total_max(self) -> int:
        return 0 if self.is_owned else self.est_price_max * self.quantity


@dataclass
class PlanResult:
    goal: KBGoal | None
    goal_key: str | None
    context: dict
    assumptions: list[Assumption]
    requirements: list[PlannedRequirement]

    @property
    def to_buy(self) -> list[PlannedRequirement]:
        return [r for r in self.requirements if not r.is_owned]

    @property
    def owned(self) -> list[PlannedRequirement]:
        return [r for r in self.requirements if r.is_owned]

    def by_priority(self, priority: str) -> list[PlannedRequirement]:
        return [r for r in self.requirements if r.priority == priority]

    @property
    def estimated_range(self) -> tuple[int, int]:
        return (
            sum(r.est_total_min for r in self.to_buy),
            sum(r.est_total_max for r in self.to_buy),
        )


def _distinctive(text: str) -> str:
    """Strip domain filler, leaving the noun that identifies the item."""
    tokens = re.findall(r"[a-z]+", text.lower())
    core = [t for t in tokens if t not in GENERIC_TOKENS and len(t) > 2]
    # If a phrase is entirely filler ("winter gear"), keep it rather than
    # matching everything on an empty string.
    return " ".join(core or tokens)


# A search term is a retrieval hint, not an identity. "Dry Bag" lists
# "backpack rain cover" as a search term, which made "backpack" score as
# highly against the dry bag as against the actual backpack.
SEARCH_TERM_WEIGHT = 0.88


def _ownership_score(owned: str, item: KBItem) -> float:
    """How strongly `owned` refers to `item`, on the distinctive words only."""
    owned_core = _distinctive(owned)
    if not owned_core:
        return 0.0

    identity = [(item.item_name, 1.0), (item.key.replace("_", " "), 1.0)]
    hints = [(term, SEARCH_TERM_WEIGHT) for term in item.search_terms]

    best = 0.0
    for candidate, weight in identity + hints:
        candidate_core = _distinctive(candidate)
        if not candidate_core:
            continue
        best = max(best, fuzz.token_set_ratio(owned_core, candidate_core) * weight)
    return best


def assign_existing_items(items: list[KBItem], existing: list[str]) -> dict[str, str]:
    """Map KB item key -> the phrase the user used, for things they own.

    Each phrase claims at most ONE requirement: its single best match. Marking
    every item above a threshold is how "trekking shoes" ends up excluding
    socks and poles too. Under-matching is recoverable (the user can tick an
    item as owned in the UI); over-matching silently drops gear they need.
    """
    assigned: dict[str, str] = {}
    for owned in existing:
        phrase = owned.strip()
        if len(phrase) < 3:
            continue
        scored = [(_ownership_score(phrase, item), item) for item in items]
        scored.sort(key=lambda s: -s[0])
        if not scored or scored[0][0] < OWNERSHIP_MATCH_THRESHOLD:
            continue
        best_score, best_item = scored[0]
        # A phrase that fits two items almost equally well is ambiguous
        # ("bag" -> backpack or dry bag). Leave it for the user to confirm.
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if best_score - runner_up < 6 and runner_up >= OWNERSHIP_MATCH_THRESHOLD:
            log.info("Ambiguous owned item %r (%s vs next %s) -- not excluded",
                     phrase, best_score, runner_up)
            continue
        assigned.setdefault(best_item.key, phrase)
    return assigned


def _resolve_priority(item: KBItem, context: dict) -> str:
    """Context can promote an item, e.g. trekking poles become essential for a
    beginner on a multi-day trek. This is where the plan stops being a static
    checklist."""
    if item.priority == Priority.ESSENTIAL:
        return item.priority
    for expr in item.promote_to_essential_when:
        if evaluate_condition(expr, context, default=False):
            return Priority.ESSENTIAL
    return item.priority


def plan_requirements(
    goal_key: str | None,
    context: dict,
    existing_items: list[str] | None = None,
    goal_text: str = "",
) -> PlanResult:
    """Turn a goal plus context into a structured, de-duplicated requirement list."""
    goal = get_goal(goal_key) or resolve_goal_from_text(goal_text or context.get("goal_text", ""))

    if goal is None:
        log.warning("No KB goal resolved for %r / %r", goal_key, goal_text[:60])
        ctx, assumptions = infer_context(context)
        return PlanResult(None, None, ctx, assumptions, [])

    # Goal defaults sit *under* whatever the user actually told us.
    merged = {**goal.context_defaults, **{k: v for k, v in context.items() if v is not None}}
    ctx, assumptions = infer_context(merged)

    existing = [e for e in (existing_items or []) if e and e.strip()]
    requirements: list[PlannedRequirement] = []

    # Only items that survive their conditions can be claimed as owned --
    # otherwise "I have a tent" would mark a tent the plan never asked for.
    applicable = [
        item for item in goal.items
        if not item.conditions
        or all(evaluate_condition(c, ctx, default=False) for c in item.conditions)
    ]
    owned_map = assign_existing_items(applicable, existing)

    for item in applicable:
        quantity = evaluate_quantity(item.quantity_rule, ctx, default=1)
        matched = owned_map.get(item.key)

        requirements.append(
            PlannedRequirement(
                kb_item_key=item.key,
                item_name=item.item_name,
                category=item.category,
                subcategory=item.subcategory,
                priority=_resolve_priority(item, ctx),
                quantity=quantity,
                reason=item.reason,
                est_price_min=item.est_price_min,
                est_price_max=item.est_price_max,
                search_terms=item.search_terms,
                required_features=item.required_features,
                preferred_features=item.preferred_features,
                is_owned=matched is not None,
                owned_matched_from=matched,
            )
        )

    requirements.sort(key=lambda r: (PRIORITY_ORDER.get(r.priority, 9), r.item_name))
    return PlanResult(goal, goal.key, ctx, assumptions, requirements)


# --------------------------------------------------------------------------
# Mode A: a named product becomes a one-line requirement
# --------------------------------------------------------------------------
_QUERY_LEADIN = re.compile(
    r"^\s*(?:can you\s+|please\s+)?"
    r"(?:find(?:\s+me)?|looking for|look for|show me|i need|i want|i'?m looking for|"
    r"search for|buy|get me|recommend|suggest)\s+(?:a|an|some|the)?\s*",
    re.I,
)
_PRICE_CLAUSE = re.compile(
    r"\b(?:under|below|less than|within|upto|up to|max(?:imum)?|around|about|budget of)\s*"
    r"(?:rs\.?|inr|₹)?\s*[\d][\d,]*\s*(?:k|thousand|lakhs?)?\b",
    re.I,
)
_TRAILING_JUNK = re.compile(r"\b(?:please|thanks|thank you)\b|[.!?]+\s*$", re.I)

# Words users type that map onto the controlled feature vocabulary.
FEATURE_SYNONYMS: dict[str, str] = {
    "water proof": "waterproof", "water-proof": "waterproof",
    "water resistant": "water_resistant", "water-resistant": "water_resistant",
    "wind proof": "windproof", "wind-proof": "windproof",
    "quick drying": "quick_dry", "quick-dry": "quick_dry", "fast drying": "quick_dry",
    "non slip": "anti_slip", "non-slip": "anti_slip", "grippy": "high_grip",
    "light weight": "lightweight", "light-weight": "lightweight", "light": "lightweight",
    "warm": "thermal", "insulating": "insulated",
    "rechargable": "rechargeable", "usb rechargeable": "rechargeable",
    "spill proof": "leak_proof", "leak proof": "leak_proof",
    "packable": "compact", "travel friendly": "portable", "foldable": "foldable",
}


def _detect_features(text: str) -> list[str]:
    from app.core.constants import FEATURES

    lowered = f" {text.lower()} "
    found: list[str] = []
    for feature in FEATURES:
        if f" {feature.replace('_', ' ')} " in lowered or f" {feature} " in lowered:
            found.append(feature)
    for phrase, feature in FEATURE_SYNONYMS.items():
        if f" {phrase} " in lowered and feature not in found:
            found.append(feature)
    return found


def _detect_category(text: str) -> str:
    from app.core.constants import CATEGORIES

    lowered = f" {text.lower()} "
    for category in CATEGORIES:
        if f" {category.replace('_', ' ')} " in lowered:
            return category
    return ""


ADHOC_KEY = "adhoc_search"


def adhoc_requirement(query: str, price_max: int | None = None) -> PlannedRequirement:
    """Turn "find waterproof trekking shoes under Rs 3,000" into a requirement.

    Mode A reuses the entire Mode B pipeline -- retrieval, scoring, badges,
    explanations -- by expressing the user's query as a single requirement.
    One code path means one set of bugs.
    """
    cleaned = _QUERY_LEADIN.sub("", query.strip())
    cleaned = _PRICE_CLAUSE.sub(" ", cleaned)
    cleaned = _TRAILING_JUNK.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")

    item_name = (cleaned or query.strip())[:120]
    features = _detect_features(query)

    return PlannedRequirement(
        kb_item_key=ADHOC_KEY,
        item_name=item_name.title() if item_name.islower() else item_name,
        category=_detect_category(query),
        subcategory="",
        priority=Priority.ESSENTIAL,
        quantity=1,
        reason="You asked for this specifically.",
        est_price_min=0,
        est_price_max=int(price_max) if price_max else 0,
        search_terms=[item_name] if item_name else [query.strip()[:120]],
        required_features=[],
        # Stated features guide the ranking rather than hard-filtering, so a
        # near-perfect product is never hidden because one tag is missing.
        preferred_features=features,
    )


def unmatched_existing_items(result: PlanResult, existing_items: list[str]) -> list[str]:
    """Things the user says they own that no requirement claimed.

    Worth surfacing: it usually means our KB is missing an item, and it stops
    us silently ignoring what the user told us.
    """
    claimed = {r.owned_matched_from for r in result.owned if r.owned_matched_from}
    return [e.strip() for e in existing_items if e.strip() and e.strip() not in claimed]
