"""Which question to ask next, and when to stop asking.

Master prompt section 11: ask only what materially changes the recommendation.
An agent that interrogates the user for six turns is a failed demo, so this
module is deliberately conservative -- it prefers inference and a stated
assumption over a question.

Owner: Member 5 (Agentic AI) with Member 4 (Requirements).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.config import settings
from app.core.constants import Intent
from app.kb.condition_dsl import evaluate_condition
from app.schemas.agent import Slots

log = logging.getLogger("smartbuy.slots")

ASKABLE_CRITICALITY = {"CRITICAL", "HIGH", "MEDIUM"}
# Slots that make a real difference to what we recommend, used for progress.
PROGRESS_SLOTS = ("activity", "budget_total", "duration_days", "location",
                  "experience_level", "camping")


@dataclass
class SlotRule:
    name: str
    criticality: str = "LOW"
    inferable: bool = True
    question: str = ""
    chips: list[str] = None
    applies_to: list[str] = None
    only_when: str | None = None
    never_ask: bool = False

    def __post_init__(self) -> None:
        self.chips = self.chips or []
        self.applies_to = self.applies_to or []


@dataclass
class SlotPolicy:
    rules: dict[str, SlotRule]
    ask_order: list[str]
    intent_overrides: dict[str, dict]

    def max_questions(self, intent: Intent | None) -> int:
        override = self.intent_overrides.get(str(intent or ""), {})
        return int(override.get("max_questions", settings.MAX_FOLLOWUP_QUESTIONS))

    def required_slots(self, intent: Intent | None) -> list[str] | None:
        override = self.intent_overrides.get(str(intent or ""), {})
        return override.get("required")


@lru_cache(maxsize=1)
def load_slot_policy() -> SlotPolicy:
    path = Path(settings.SLOT_POLICY_PATH)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    rules: dict[str, SlotRule] = {}
    for name, cfg in (raw.get("slots") or {}).items():
        rules[name] = SlotRule(
            name=name,
            criticality=str(cfg.get("criticality", "LOW")).upper(),
            inferable=bool(cfg.get("inferable", True)),
            question=cfg.get("question", ""),
            chips=list(cfg.get("chips") or []),
            applies_to=list(cfg.get("applies_to") or []),
            only_when=cfg.get("only_when"),
            never_ask=bool(cfg.get("never_ask", False)),
        )

    return SlotPolicy(
        rules=rules,
        ask_order=list(raw.get("ask_order") or list(rules)),
        intent_overrides={k: v or {} for k, v in (raw.get("intent_overrides") or {}).items()},
    )


def _value(slots: Slots, name: str):
    return getattr(slots, name, None)


def _is_empty(value) -> bool:
    return value is None or value == "" or value == []


def collected(slots: Slots) -> list[str]:
    """Slots the user has actually supplied."""
    out = [name for name in PROGRESS_SLOTS if not _is_empty(_value(slots, name))]
    if slots.existing_items:
        out.append("existing_items")
    return out


def askable(slots: Slots, intent: Intent | None,
            asked: set[str] | None = None) -> list[str]:
    """Empty slots we are permitted to ask about, in policy order.

    `asked` holds slots we have already put to the user. They stay excluded
    even if the answer did not resolve them -- "not sure yet" is an answer,
    and asking the same question twice is worse than proceeding on a default.
    """
    policy = load_slot_policy()
    context = slots.to_context()
    asked = asked or set()

    required = policy.required_slots(intent)
    out: list[str] = []

    for name in policy.ask_order:
        rule = policy.rules.get(name)
        if rule is None or rule.never_ask or name in asked:
            continue
        if rule.criticality not in ASKABLE_CRITICALITY:
            continue
        if not _is_empty(_value(slots, name)):
            continue
        # Mode A and the refinement intents have their own short list.
        if required is not None:
            if name not in required:
                continue
        elif rule.applies_to and intent and str(intent) not in rule.applies_to:
            continue
        # e.g. only ask about camping for trek-shaped activities.
        if rule.only_when and not evaluate_condition(rule.only_when, context, default=False):
            continue
        out.append(name)

    return out


def missing(slots: Slots, intent: Intent | None,
            asked: set[str] | None = None) -> list[str]:
    return askable(slots, intent, asked)


def next_question(slots: Slots, intent: Intent | None, question_count: int,
                  asked: set[str] | None = None) -> tuple[str, str, list[str]] | None:
    """Return (slot_name, default_wording, chips), or None to stop asking.

    Stopping is a feature. Once the cap is reached we proceed with inferred
    defaults and show them as correctable assumptions.
    """
    policy = load_slot_policy()
    if question_count >= policy.max_questions(intent):
        return None

    pending = askable(slots, intent, asked)
    if not pending:
        return None

    rule = policy.rules[pending[0]]
    return rule.name, rule.question, list(rule.chips)


def progress(slots: Slots, intent: Intent | None,
             asked: set[str] | None = None) -> float:
    """0..1 for the sidebar progress indicator."""
    if intent in (Intent.PRODUCT_COMPARISON, Intent.FIND_BEST_DEAL,
                  Intent.FIND_ALTERNATIVE):
        return 1.0

    relevant = [s for s in PROGRESS_SLOTS
                if s == "activity" or s in load_slot_policy().ask_order]
    if not relevant:
        return 1.0

    known = sum(1 for s in relevant if not _is_empty(_value(slots, s)))
    if not askable(slots, intent, asked):
        return 1.0
    return round(min(0.95, known / max(1, len(relevant))), 2)


def ready_to_plan(slots: Slots, intent: Intent | None, question_count: int,
                  asked: set[str] | None = None) -> bool:
    """True when there is nothing left we are permitted to ask.

    Deliberately identical to "no next question": this YAML is the single
    source of truth for how inquisitive the agent is. An extra escape hatch
    here would let the agent skip the one question that changes the plan --
    "camping overnight or guesthouses?" decides whether a tent and sleeping
    bag appear at all.
    """
    return next_question(slots, intent, question_count, asked) is None
