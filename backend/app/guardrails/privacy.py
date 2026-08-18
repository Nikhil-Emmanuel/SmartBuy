"""Privacy scrub -- runs on every string that leaves for the LLM.

Master prompt section 30: only provide necessary user data to the LLM. Two
mechanisms here:

  1. redact()  -- removes contact details and identifiers from free text.
  2. minimal_slots() -- an allow-list, so a slot we add later is not silently
     shipped to a third party just because it exists on the model.

Owner: Member 6 (Responsible AI).
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
# Indian mobile numbers, with or without +91 and separators.
_PHONE = re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{9}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_AADHAAR = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_UPI = re.compile(r"\b[\w.-]{3,}@(?:okhdfcbank|okaxis|oksbi|ybl|paytm|upi|ibl)\b", re.I)
_PINCODE = re.compile(r"\b[1-9]\d{5}\b")

# Order matters: the most specific patterns run first so a card number is not
# partially eaten by the pincode rule.
_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_EMAIL, "[email]"),
    (_UPI, "[upi]"),
    (_AADHAAR, "[id]"),
    (_PAN, "[id]"),
    (_CARD, "[card]"),
    (_PHONE, "[phone]"),
    (_PINCODE, "[pincode]"),
)

# Slots the LLM is allowed to see. Everything else stays server-side.
LLM_VISIBLE_SLOTS: frozenset[str] = frozenset({
    "goal_text", "activity", "location", "region_type", "season", "start_date",
    "duration_days", "people_count", "experience_level", "budget_total",
    "currency", "camping", "temp_min_c", "existing_items",
})


def redact(text: str | None) -> str:
    """Strip contact details and identifiers from free text."""
    if not text:
        return ""
    out = text
    for pattern, replacement in _RULES:
        out = pattern.sub(replacement, out)
    return out


def contains_pii(text: str | None) -> bool:
    return bool(text) and redact(text) != text


def minimal_slots(slots: dict) -> dict:
    """Allow-listed slot dict for prompts, with free text redacted."""
    out: dict = {}
    for key in LLM_VISIBLE_SLOTS:
        if key not in slots:
            continue
        value = slots[key]
        if value in (None, "", [], {}):
            continue
        if key == "goal_text":
            value = redact(str(value))[:500]
        elif key == "location":
            value = redact(str(value))[:80]
        elif key == "existing_items":
            value = [redact(str(v))[:60] for v in value][:20]
        out[key] = value
    return out


def summarise_for_audit(text: str | None, limit: int = 200) -> str:
    """What we are willing to persist in audit_logs: redacted and truncated."""
    cleaned = redact(text).strip()
    return cleaned[:limit] + ("..." if len(cleaned) > limit else "")
