"""LLM call #3 -- turning a computed score into an explanation.

The contract is narrow on purpose. Python has already decided what to
recommend and why; the model's only job is to say it well. If it introduces a
number we did not give it, the grounding guardrail rejects the whole output
and we ship the deterministic reasons instead.

That means "explanation quality" degrades gracefully but "explanation
truthfulness" never does.

Owner: Member 5 (Agentic AI) with Member 6 (Responsible AI).
"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.agent.llm import get_llm_provider
from app.agent.prompts import explanation_prompt
from app.core.constants import SOURCE_DISPLAY_NAMES
from app.guardrails.recommendation_checks import check_explanation
from app.logging import audit
from app.services.ranking import weighted_points

log = logging.getLogger("smartbuy.explain")

EXPLAINABLE_CONTEXT_KEYS = (
    "activity", "location", "season", "region_type", "duration_days",
    "experience_level", "budget_total", "camping", "people_count",
)


def product_evidence(product) -> dict:
    """Exactly what the model is allowed to know about a product."""
    return {
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "subcategory": product.subcategory,
        "price": int(product.price),
        "original_price": int(product.original_price),
        "discount_pct": int(product.discount_pct),
        "rating": float(product.rating),
        "review_count": int(product.review_count),
        "delivery_days": int(product.delivery_days),
        "availability": product.availability,
        "features": list(product.features or []),
        "tags": list(product.tags or []),
        "marketplace": SOURCE_DISPLAY_NAMES.get(product.source, product.source),
        "is_simulated": True,
    }


def explain(
    db: Session | None,
    product,
    breakdown: dict,
    context: dict,
    fallback_reasons: list[str],
    preset: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Explain one recommendation.

    Always returns something usable:
        {"summary", "reasons", "grounded", "degraded"}
    `grounded` is False whenever the prose came from the deterministic layer.
    """
    facts = list(fallback_reasons or [])
    points = weighted_points(breakdown or {}, preset)
    evidence = product_evidence(product)
    safe_context = {k: context.get(k) for k in EXPLAINABLE_CONTEXT_KEYS
                    if context.get(k) not in (None, "", [])}

    default = {
        "summary": facts[0] if facts else "",
        "reasons": facts[:5],
        "grounded": False,
        "degraded": True,
    }

    provider = get_llm_provider()
    if not provider.available:
        return default

    system, user_prompt = explanation_prompt(
        product=evidence,
        breakdown={k: round(float(v), 3) for k, v in (breakdown or {}).items()},
        points=points,
        context=safe_context,
        facts=facts,
    )

    started = time.perf_counter()
    try:
        payload = provider.generate_json(system, user_prompt, max_output_tokens=500)
    except Exception as exc:  # noqa: BLE001 - any failure means fall back
        audit.record(db, action="llm_call", tool="explain", session_id=session_id,
                     input_summary=product.name, output_summary=str(exc),
                     model_version=provider.model, status=audit.STATUS_FALLBACK,
                     latency_ms=int((time.perf_counter() - started) * 1000))
        return default

    # The model may only mention numbers that appear in what we sent it.
    all_evidence = [evidence, breakdown, points, safe_context, facts]
    summary, reasons, grounded = check_explanation(payload, all_evidence, facts)

    audit.record(
        db, action="llm_call", tool="explain", session_id=session_id,
        input_summary=product.name,
        output_summary=summary or "rejected by grounding guardrail",
        model_version=provider.model,
        status=audit.STATUS_OK if grounded else audit.STATUS_BLOCKED,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    if not grounded:
        return default

    return {
        "summary": summary or (facts[0] if facts else ""),
        "reasons": reasons,
        "grounded": True,
        "degraded": False,
    }
