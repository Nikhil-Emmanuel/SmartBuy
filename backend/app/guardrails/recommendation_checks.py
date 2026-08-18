"""Grounding guardrail for generated explanations.

The rule from docs/ARCHITECTURE.md: the LLM may phrase a recommendation but may
not introduce a fact. Concretely, every number in an explanation must already
appear in the evidence we supplied, and certain claims are forbidden outright
because we cannot honestly make them -- we have a simulated catalog, not a live
price feed.

A rejected explanation is not an error. We fall back to the deterministic
reason strings the ranking engine produced, which are always true by
construction.

Owner: Member 6 (Responsible AI).
"""

from __future__ import annotations

import logging
import re

log = logging.getLogger("smartbuy.guardrails")

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Claims we can never substantiate. Checked case-insensitively on the output.
BANNED_CLAIMS: tuple[tuple[str, str], ...] = (
    (r"real[- ]?time price", "claims real-time pricing"),
    (r"live price", "claims live pricing"),
    (r"\bguarantee(?:d|s)?\b", "unqualified guarantee"),
    (r"lowest price (?:on the )?(?:internet|market|anywhere)", "unverifiable superlative"),
    (r"cheapest (?:on the )?(?:internet|market|anywhere)", "unverifiable superlative"),
    (r"price will (?:drop|fall|rise)", "price prediction"),
    (r"\b(?:amazon|flipkart|myntra|ajio|meesho)\b", "names a real marketplace"),
    (r"free (?:shipping|delivery) on all", "unverifiable shipping claim"),
    (r"\b100% (?:safe|waterproof|reliable)\b", "absolute product claim"),
    (r"medically|clinically proven", "unsupported health claim"),
)

_BANNED = tuple((re.compile(p, re.I), reason) for p, reason in BANNED_CLAIMS)

# Numbers so generic that requiring evidence for them produces false rejections
# ("one of the three picks", "2 of 5 requirements").
_TRIVIAL = {"0", "1", "2", "3", "4", "5"}


def numbers_in(text: str) -> set[str]:
    """Normalised numeric tokens: '1,599' and '1599.0' both become '1599'."""
    found: set[str] = set()
    for raw in _NUMBER.findall(text or ""):
        found.add(_normalise(raw))
    return found


def _normalise(raw: str) -> str:
    value = raw.replace(",", "")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value or "0"


def evidence_numbers(evidence) -> set[str]:
    """Every number anywhere in the evidence, plus common rounded forms.

    A rating of 4.35 legitimately reads as "4.4 stars", and a saving of 6,600
    legitimately reads as "6,600" or "6600", so we pre-compute the variants a
    truthful writer would use rather than punishing them.
    """
    allowed: set[str] = set(_TRIVIAL)
    for token in _walk(evidence):
        allowed.add(_normalise(token))
        try:
            number = float(token.replace(",", ""))
        except ValueError:
            continue
        allowed.add(_normalise(f"{round(number, 1):.1f}"))
        allowed.add(_normalise(str(int(number))))
        allowed.add(_normalise(str(round(number))))
        # Percentages are frequently stated to the nearest whole number.
        if 0 < number < 100:
            allowed.add(str(int(number)))
    return allowed


def _walk(node) -> list[str]:
    """Collect numeric tokens from an arbitrarily nested evidence structure."""
    out: list[str] = []
    if node is None or isinstance(node, bool):
        return out
    if isinstance(node, (int, float)):
        out.append(str(node))
    elif isinstance(node, str):
        out.extend(_NUMBER.findall(node))
    elif isinstance(node, dict):
        for key, value in node.items():
            out.extend(_NUMBER.findall(str(key)))
            out.extend(_walk(value))
    elif isinstance(node, (list, tuple, set)):
        for value in node:
            out.extend(_walk(value))
    return out


def check_grounding(text: str, evidence) -> tuple[bool, str]:
    """(ok, reason). Reason is empty when the text passes."""
    if not text or not text.strip():
        return False, "empty"

    for pattern, reason in _BANNED:
        if pattern.search(text):
            return False, reason

    allowed = evidence_numbers(evidence)
    unsupported = sorted(numbers_in(text) - allowed)
    if unsupported:
        return False, f"unsupported numbers: {', '.join(unsupported[:5])}"

    return True, ""


def check_explanation(payload: dict, evidence, fallback_reasons: list[str],
                      max_reasons: int = 5) -> tuple[str, list[str], bool]:
    """Validate an explanation payload from the LLM.

    Returns (summary, reasons, grounded). When grounded is False the caller
    should surface the deterministic reasons instead -- the caller decides,
    this function never raises.
    """
    if not isinstance(payload, dict):
        return "", list(fallback_reasons[:max_reasons]), False

    summary = str(payload.get("summary") or "").strip()
    raw_reasons = payload.get("reasons")
    reasons = [str(r).strip() for r in raw_reasons] if isinstance(raw_reasons, list) else []
    reasons = [r for r in reasons if r][:max_reasons]

    if not summary and not reasons:
        return "", list(fallback_reasons[:max_reasons]), False

    combined = " ".join([summary, *reasons])
    ok, reason = check_grounding(combined, evidence)
    if not ok:
        log.warning("Explanation rejected by grounding guardrail (%s)", reason)
        return "", list(fallback_reasons[:max_reasons]), False

    return summary, reasons or list(fallback_reasons[:max_reasons]), True


def check_question(payload: dict, default_question: str,
                   default_chips: list[str]) -> tuple[str, list[str]]:
    """Validate a rephrased follow-up question.

    The model is allowed to be friendly, not to invent numbers or ask two
    things at once. Anything suspicious falls back to the template.
    """
    if not isinstance(payload, dict):
        return default_question, default_chips

    question = str(payload.get("question") or "").strip()
    if not question or len(question) > 220:
        return default_question, default_chips
    if question.count("?") > 1:
        return default_question, default_chips
    for pattern, _ in _BANNED:
        if pattern.search(question):
            return default_question, default_chips
    # A question should not contain a figure we did not give it.
    if numbers_in(question) - set(_TRIVIAL) - numbers_in(" ".join(default_chips)) - \
            numbers_in(default_question):
        return default_question, default_chips

    raw_chips = payload.get("chips")
    chips = [str(c).strip()[:32] for c in raw_chips] if isinstance(raw_chips, list) else []
    chips = [c for c in chips if c][:4]

    return question, chips or default_chips
