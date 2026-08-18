"""Input validation and prompt-injection defence.

Two directions of distrust:
  - User text may try to reprogram the agent. We neutralise it and flag it,
    but we never refuse to shop -- the user still gets their plan.
  - LLM output may try to write arbitrary fields. Everything the model returns
    is passed through an explicit coercion layer before it touches a slot or
    the database. Master prompt section 31: the LLM never writes to the DB
    directly.

Owner: Member 6 (Responsible AI).
"""

from __future__ import annotations

import re
import unicodedata

from app.core.constants import Intent

MAX_MESSAGE_CHARS = 2000

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"[ \t]{3,}")

# Phrases that only appear when someone is talking to the model rather than
# about shopping. Detection is advisory: we log and continue.
INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I) for p in (
        r"ignore (?:all |any |the )?(?:previous|prior|above|earlier) (?:instructions?|prompts?|rules?)",
        r"disregard (?:all |the )?(?:previous|prior|above) ",
        r"you are now (?:a|an|no longer)",
        r"forget (?:everything|all previous|your instructions)",
        r"(?:system|developer)\s*(?:prompt|message)\s*[:>]",
        r"reveal (?:your|the) (?:system )?(?:prompt|instructions|rules)",
        r"</?\s*(?:data|system|instruction)s?\s*>",
        r"\bact as (?:a |an )?(?:different|new|unrestricted)",
        r"\bDAN\b|\bjailbreak\b",
        r"print (?:your|the) (?:api[_ ]?key|secret|token)",
        r"set (?:the )?(?:price|rating|score|discount) (?:to|=)",
        r"always recommend",
    )
)

# Angle brackets are how we delimit untrusted blocks in prompts, so user text
# containing them is defanged rather than passed through.
_TAGS = re.compile(r"<\s*/?\s*(data|system|instruction|assistant|user)[^>]*>", re.I)


def sanitize_message(text: str) -> str:
    """Normalise user input before it is stored or sent anywhere."""
    if not text:
        return ""
    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = _CONTROL.sub(" ", cleaned)
    cleaned = _TAGS.sub(" ", cleaned)
    cleaned = _WHITESPACE.sub("  ", cleaned)
    cleaned = "\n".join(line.rstrip() for line in cleaned.splitlines())
    return cleaned.strip()[:MAX_MESSAGE_CHARS]


def detect_injection(text: str) -> list[str]:
    """Return the patterns that matched. Empty list means clean."""
    if not text:
        return []
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


def wrap_untrusted(text: str, kind: str = "user_message") -> str:
    """Wrap catalog or user text for a prompt, with tags already stripped."""
    return f'<data type="{kind}">\n{sanitize_message(text)}\n</data>'


# --------------------------------------------------------------------------
# LLM output coercion
# --------------------------------------------------------------------------
_ALLOWED_EXPERIENCE = {"beginner", "intermediate", "experienced"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MIN_BUDGET = 100
MAX_BUDGET = 10_000_000


def coerce_intent(value) -> Intent | None:
    try:
        return Intent(str(value).strip().upper())
    except (ValueError, AttributeError):
        return None


def _as_int(value, low: int, high: int) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None
    return number if low <= number <= high else None


def _as_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "y"):
            return True
        if lowered in ("false", "no", "n"):
            return False
    return None


def coerce_slots(raw: dict, allowed_activities: set[str]) -> dict:
    """Turn a model's slot object into values we are willing to store.

    Anything unrecognised is dropped rather than corrected -- a wrong slot is
    worse than a missing one, because a missing one gets asked about.
    """
    if not isinstance(raw, dict):
        return {}

    out: dict = {}

    activity = raw.get("activity")
    if isinstance(activity, str) and activity.strip().lower() in allowed_activities:
        out["activity"] = activity.strip().lower()

    location = raw.get("location")
    if isinstance(location, str) and 1 < len(location.strip()) <= 80:
        out["location"] = location.strip()[:80]

    duration = _as_int(raw.get("duration_days"), 1, 365)
    if duration is not None:
        out["duration_days"] = duration

    people = _as_int(raw.get("people_count"), 1, 50)
    if people is not None:
        out["people_count"] = people

    experience = raw.get("experience_level")
    if isinstance(experience, str) and experience.strip().lower() in _ALLOWED_EXPERIENCE:
        out["experience_level"] = experience.strip().lower()

    budget = _as_int(raw.get("budget_total"), MIN_BUDGET, MAX_BUDGET)
    if budget is not None:
        out["budget_total"] = budget

    camping = _as_bool(raw.get("camping"))
    if camping is not None:
        out["camping"] = camping

    start_date = raw.get("start_date")
    if isinstance(start_date, str) and _DATE.match(start_date.strip()):
        out["start_date"] = start_date.strip()

    return out


def coerce_existing_items(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for entry in raw[:20]:
        if not isinstance(entry, str):
            continue
        item = re.sub(r"[^a-zA-Z0-9\s\-]", " ", entry).strip().lower()
        item = re.sub(r"\s+", " ", item)
        if 2 < len(item) <= 60:
            items.append(item)
    return list(dict.fromkeys(items))


def coerce_confidence(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, number))
