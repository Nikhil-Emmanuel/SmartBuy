"""Recommendations and explanations. API contract section 4."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.agent.explain import explain as explain_recommendation
from app.api.deps import CurrentUser, DbSession
from app.api.serializers import best_offer, recommendation_out, requirement_out
from app.core.errors import ProductNotFound, RequirementNotFound
from app.models.plan import Requirement
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.schemas.common import ScoreBreakdown, WeightedPoint
from app.schemas.recommendation import (
    ExplainRequest,
    ExplainResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    RequirementResults,
)
from app.services import plan_service
from app.services.ranking import weighted_points

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(payload: RecommendationsRequest,
                        db: DbSession) -> RecommendationsResponse:
    plan = plan_service.get_plan(db, payload.plan_id)

    wanted = set(payload.requirement_ids or [])
    requirements = [r for r in plan.requirements
                    if not wanted or r.id in wanted]

    rows = db.scalars(
        select(Recommendation)
        .where(Recommendation.plan_id == plan.id)
        .order_by(Recommendation.rank)
    ).all()

    by_requirement: dict[str, list[Recommendation]] = {}
    for row in rows:
        by_requirement.setdefault(row.requirement_id, []).append(row)

    results: list[RequirementResults] = []
    for requirement in requirements:
        if requirement.is_owned:
            continue
        recs = by_requirement.get(requirement.id, [])[:payload.limit_per_requirement]
        results.append(RequirementResults(
            requirement=requirement_out(requirement),
            recommendations=[
                recommendation_out(r, best_offer(db, r.product_id)) for r in recs
            ],
            unfulfilled_reason=None if recs else (
                requirement.unfulfilled_reason or "no_candidates"
            ),
        ))

    return RecommendationsResponse(plan_id=plan.id, results=results)


@router.post("/explain", response_model=ExplainResponse)
def explain(payload: ExplainRequest, db: DbSession, user: CurrentUser) -> ExplainResponse:
    """The Page 7 scorecard.

    Every number here is computed in Python. Only `summary` and the wording of
    `reasons` may come from the model, and only if they survive the grounding
    guardrail.
    """
    product = db.get(Product, payload.product_id)
    if product is None:
        raise ProductNotFound(f"No product with id {payload.product_id}.")

    breakdown: dict = {}
    reasons: list[str] = []
    context: dict = {}
    preset: str | None = None
    session_id: str | None = None

    if payload.requirement_id:
        requirement = db.get(Requirement, payload.requirement_id)
        if requirement is None:
            raise RequirementNotFound(f"No requirement with id {payload.requirement_id}.")

        plan = plan_service.get_plan(db, requirement.plan_id)
        context = dict(plan.context or {})
        session_id = plan.session_id

        stored = db.scalars(
            select(Recommendation).where(
                Recommendation.requirement_id == requirement.id,
                Recommendation.product_id == product.id,
            )
        ).first()

        if stored is not None:
            breakdown = dict(stored.score_breakdown or {})
            reasons = list(stored.reasons or [])
        else:
            # Not one of the stored top picks -- score it on demand so the user
            # can still ask "why not this one?".
            candidates = plan_service.rank_for_requirement(db, plan, requirement, user)
            match = next((c for c in candidates if c.product.id == product.id), None)
            if match is not None:
                breakdown = dict(match.breakdown)
                reasons = list(match.reasons)

    prose = explain_recommendation(
        db, product, breakdown, context, reasons, preset=preset, session_id=session_id
    )
    db.commit()

    return ExplainResponse(
        match_score=round(float(breakdown.get("final", 0.0)), 4),
        score_breakdown=ScoreBreakdown(**breakdown),
        weighted_points=[WeightedPoint(**p) for p in weighted_points(breakdown, preset)],
        summary=prose["summary"],
        reasons=prose["reasons"],
        evidence={
            "price": int(product.price),
            "original_price": int(product.original_price),
            "discount_pct": int(product.discount_pct),
            "rating": float(product.rating),
            "review_count": int(product.review_count),
            "delivery_days": int(product.delivery_days),
            "availability": product.availability,
            "features": list(product.features or []),
            "is_simulated": True,
        },
        llm_generated=prose["grounded"],
    )
