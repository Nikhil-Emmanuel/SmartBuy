"""Deterministic NLU -- the path taken when the LLM is unavailable.

This is demo insurance and it is not a stub. LLM APIs rate-limit, time out and
have keys revoked, and it always happens during the presentation. Everything
here runs on regex and lookup tables, produces the same slot dict the LLM
would, and lets the full journey complete with templated language.

Member 8 tests this by revoking the API key and running the demo end to end.

Owner: Member 5 (Agentic AI).
"""

from __future__ import annotations

import re

from app.core.constants import Intent
from app.kb.loader import resolve_goal_from_text
from app.schemas.agent import Slots
from app.services.context_inference import LOCATIONS

# --------------------------------------------------------------------------
# Intent
# --------------------------------------------------------------------------
INTENT_PATTERNS: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.PRODUCT_COMPARISON,
     ("compare", " vs ", " versus ", "difference between", "which is better")),
    (Intent.FIND_ALTERNATIVE,
     ("alternative", "instead of", "something else", "other options",
      "replace this", "swap this", "different option")),
    (Intent.BUDGET_OPTIMIZATION,
     ("too expensive", "reduce the cost", "lower the total", "within my budget",
      "cheaper overall", "bring it down", "optimize my budget", "cut the cost")),
    (Intent.FIND_BEST_DEAL,
     ("best deal", "best offer", "biggest discount", "best price",
      "cheapest", "any offers", "on sale")),
    (Intent.GOAL_BASED_SHOPPING,
     ("what do i need", "what should i buy", "everything for", "planning a",
      "planning to", "i'm going", "im going", "i am going", "going for",
      "setting up", "getting ready for", "prepare for", "help me plan",
      "shopping list", "packing list", "first apartment", "moving into")),
    (Intent.SPECIFIC_PRODUCT_SEARCH,
     ("find me", "looking for", "show me", "i need a", "i want a",
      "search for", "buy a", "recommend a")),
]


# A goal word alone is not a goal. "Waterproof trekking shoes under Rs 3,000"
# contains "trek" but is plainly a product lookup; "a tent for my trek" is not.
# The difference is a purpose clause or a planning verb, not the noun.
_PURPOSE = re.compile(
    r"\b(?:for|before|ahead of|during)\s+(?:my|our|the|a|an|this)?\s*"
    r"(?:\w+\s+){0,2}"
    r"(trip|trek|trekking|hike|hiking|camp|camping|expedition|holiday|vacation|"
    r"move|apartment|flat|honeymoon|wedding|semester)\b",
    re.I,
)
_PLANNING_PHRASES = (
    "planning", "i'm going", "im going", "i am going", "going for", "going on",
    "getting ready", "prepare for", "preparing for", "what do i need",
    "what should i buy", "everything for", "shopping list", "packing list",
    "help me plan", "setting up", "moving into",
)


def _looks_goal_shaped(message: str) -> bool:
    """Does this describe a situation, rather than name a product?"""
    lowered = f" {message.lower().strip()} "
    if any(p in lowered for p in _PLANNING_PHRASES) or _PURPOSE.search(lowered):
        return True
    # "Winter trek in Manali for 4 days" states no verb but is clearly a plan:
    # nobody puts a duration or a headcount on a single product.
    return extract_duration_days(message) is not None or \
        extract_people_count(message) is not None


def detect_intent(message: str, has_active_plan: bool = False) -> Intent:
    lowered = f" {message.lower().strip()} "

    for intent, needles in INTENT_PATTERNS:
        if any(n in lowered for n in needles):
            # "I need a tent for my trek" is goal-shaped, not a single-product
            # lookup -- the purpose clause outranks the product phrasing.
            if (intent == Intent.SPECIFIC_PRODUCT_SEARCH
                    and resolve_goal_from_text(lowered)
                    and _looks_goal_shaped(message)):
                return Intent.GOAL_BASED_SHOPPING
            return intent

    if resolve_goal_from_text(lowered) and _looks_goal_shaped(message):
        return Intent.GOAL_BASED_SHOPPING
    if has_active_plan:
        return Intent.GENERAL_RECOMMENDATION
    return Intent.SPECIFIC_PRODUCT_SEARCH


# --------------------------------------------------------------------------
# Slots
# --------------------------------------------------------------------------
_BUDGET_PATTERNS = (
    re.compile(r"(?:budget|spend|around|about|under|below|within|upto|up to|max(?:imum)?)"
               r"[^\d]{0,18}(?:rs\.?|inr|₹)?\s*([\d][\d,]*)\s*(k|thousand|lakhs?|lac|l)?\b",
               re.I),
    re.compile(r"(?:rs\.?|inr|₹)\s*([\d][\d,]*)\s*(k|thousand|lakhs?|lac|l)?\b", re.I),
    re.compile(r"\b([\d][\d,]*)\s*(k|thousand|lakhs?|lac)\b", re.I),
    re.compile(r"\b([\d][\d,]*)\s*(?:rupees|rs\.?)\b", re.I),
)

_MULTIPLIER = {"k": 1000, "thousand": 1000, "lakh": 100000, "lakhs": 100000,
               "lac": 100000, "l": 100000}


def extract_budget(message: str) -> int | None:
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(message)
        if not match:
            continue
        raw = match.group(1).replace(",", "")
        if not raw.isdigit():
            continue
        value = int(raw)
        suffix = (match.group(2) or "").lower() if match.lastindex and match.lastindex >= 2 else ""
        value *= _MULTIPLIER.get(suffix, 1)
        # A bare "4" from "4 days" is not a budget; require a plausible amount.
        if 100 <= value <= 10_000_000:
            return value
    return None


_DURATION = re.compile(r"\b(\d+)[\s-]*(day|night|week|month)s?\b", re.I)
_WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_WORD_DURATION = re.compile(
    r"\b(" + "|".join(_WORD_NUMBERS) + r")[\s-]*(day|night|week)s?\b", re.I)


def extract_duration_days(message: str) -> int | None:
    match = _DURATION.search(message)
    if match:
        count, unit = int(match.group(1)), match.group(2).lower()
    else:
        match = _WORD_DURATION.search(message)
        if not match:
            return None
        count, unit = _WORD_NUMBERS[match.group(1).lower()], match.group(2).lower()

    if unit == "week":
        return count * 7
    if unit == "month":
        return count * 30
    # "3 nights" is a 4-day trip in every itinerary anyone actually writes.
    return count + 1 if unit == "night" else count


_PEOPLE = re.compile(
    r"\b(\d+)\s*(?:people|persons?|pax|of us|friends|adults|members)\b", re.I)
_WORD_PEOPLE = re.compile(
    r"\b(?:we are|there are|group of|team of)\s+(\d+|" + "|".join(_WORD_NUMBERS) + r")\b", re.I)


def extract_people_count(message: str) -> int | None:
    lowered = message.lower()
    if any(p in lowered for p in ("just me", "only me", "myself", "solo", "alone")):
        return 1
    for pattern in (_PEOPLE, _WORD_PEOPLE):
        match = pattern.search(message)
        if match:
            token = match.group(1).lower()
            value = _WORD_NUMBERS.get(token) or (int(token) if token.isdigit() else None)
            if value and 1 <= value <= 50:
                return value
    return None


def extract_experience(message: str) -> str | None:
    lowered = message.lower()
    if any(p in lowered for p in ("beginner", "first time", "first-time", "never done",
                                  "new to this", "novice", "starting out", "my first")):
        return "beginner"
    if any(p in lowered for p in ("experienced", "done this before", "veteran", "expert",
                                  "many times", "regularly", "seasoned")):
        return "experienced"
    if any(p in lowered for p in ("intermediate", "a few times", "done it twice")):
        return "intermediate"
    return None


def extract_camping(message: str) -> bool | None:
    lowered = message.lower()
    if any(p in lowered for p in ("not camping", "no camping", "no tent", "guesthouse",
                                  "guest house", "homestay", "home stay", "hotel",
                                  "hostel stay", "lodge", "staying in")):
        return False
    if any(p in lowered for p in ("camping", "camp overnight", "in a tent", "tents",
                                  "sleeping outdoors", "overnight camp", "bivouac")):
        return True
    return None


def extract_location(message: str) -> str | None:
    lowered = message.lower()
    # Longest name first so "ladakh" is not shadowed by a shorter substring.
    for name in sorted(LOCATIONS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return name.title()

    match = re.search(r"\b(?:in|to|at|near|around)\s+([A-Z][a-zA-Z]{2,}(?:\s[A-Z][a-zA-Z]+)?)",
                      message)
    if match:
        candidate = match.group(1).strip()
        if candidate.lower() not in ("i", "my", "the", "a", "an"):
            return candidate
    return None


_OWNERSHIP = re.compile(
    r"(?:i\s+)?(?:already\s+)?(?:have|own|got|possess|carry)\s+(?:a\s+|an\s+|my\s+|the\s+)?"
    r"([^.!?;]+?)(?:\s*(?:\.|!|\?|;|$|,\s*(?:and\s+)?(?:i|but|so|my budget|budget)\b))",
    re.I,
)
_SPLIT = re.compile(r",|\band\b|\balso\b|\bplus\b|&|/", re.I)
_STOPWORDS = {"a", "an", "the", "my", "some", "few", "already", "got", "it", "them",
              "one", "two", "pair", "set", "of", "new", "old"}


def extract_existing_items(message: str) -> list[str]:
    """Pull "I already have shoes and a backpack" into ['shoes', 'backpack'].

    Guarded against swallowing the rest of the sentence: "I have a budget of
    Rs 15,000" must not register a product called "budget of Rs 15,000".
    """
    items: list[str] = []
    for match in _OWNERSHIP.finditer(message):
        chunk = match.group(1).strip()
        if not chunk or len(chunk) > 120:
            continue
        for piece in _SPLIT.split(chunk):
            item = " ".join(
                w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]*", piece)
                if w.lower() not in _STOPWORDS
            ).strip()
            if not item or len(item) < 3:
                continue
            lowered = item.lower()
            if any(bad in lowered for bad in
                   ("budget", "rupee", "money", "question", "idea", "plan", "time",
                    "experience", "day", "week", "problem", "issue")):
                continue
            items.append(item.lower())
    return list(dict.fromkeys(items))


def extract_price_ceiling(message: str) -> int | None:
    """"...under Rs 3,000" for Mode A -- a per-product cap, not a total budget."""
    match = re.search(
        r"\b(?:under|below|less than|within|upto|up to|max)\s*(?:rs\.?|inr|₹)?\s*"
        r"([\d][\d,]*)\s*(k|thousand)?\b", message, re.I)
    if not match:
        return None
    value = int(match.group(1).replace(",", ""))
    value *= _MULTIPLIER.get((match.group(2) or "").lower(), 1)
    return value if 100 <= value <= 10_000_000 else None


def understand(message: str, current: Slots | None = None,
               has_active_plan: bool = False) -> tuple[Intent, Slots]:
    """Deterministic counterpart to the LLM's understand() call.

    Returns the same (intent, slots) shape, so the orchestrator does not care
    which path produced it.
    """
    intent = detect_intent(message, has_active_plan)

    # Only a goal-shaped turn may set the activity. Otherwise "trekking shoes"
    # would quietly turn a product search into a full trek plan.
    goal = resolve_goal_from_text(message) if intent == Intent.GOAL_BASED_SHOPPING else None

    slots = Slots(
        goal_text=message.strip()[:500],
        activity=goal.key if goal else (current.activity if current else None),
        location=extract_location(message),
        duration_days=extract_duration_days(message),
        people_count=extract_people_count(message),
        experience_level=extract_experience(message),
        budget_total=extract_budget(message),
        camping=extract_camping(message),
        existing_items=extract_existing_items(message),
    )

    if intent == Intent.SPECIFIC_PRODUCT_SEARCH and slots.budget_total is None:
        slots.budget_total = extract_price_ceiling(message)

    return intent, slots
