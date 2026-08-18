"""Side-by-side comparison and substitution. API contract sections 4 and 5."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import product_out
from app.core.errors import ProductNotFound, RequirementNotFound
from app.models.plan import Requirement
from app.models.product import Product
from app.schemas.common import ScoreBreakdown
from app.schemas.recommendation import (
    COMPARE_COLUMNS,
    AlternativeOut,
    CompareRequest,
    CompareResponse,
    CompareRow,
    SubstituteRequest,
    SubstituteResponse,
)
from app.services import plan_service
from app.services.ranking import (
    RequirementSpec,
    ScoringContext,
    derive_context_tags,
    score_product,
)
from app.services.recommendation import build_scoring_context, find_substitutes, to_spec

router = APIRouter(prefix="/api", tags=["comparison"])

# Columns where the winner is the LOWEST value.
LOWER_IS_BETTER = {"price", "delivery_days"}


def _column_value(row: CompareRow, column: str):
    product = row.product
    return {
        "price": product.price,
        "rating": product.rating,
        "review_count": product.review_count,
        "delivery_days": product.delivery_days,
        "match_score": row.match_score,
        "deal_value": row.deal_value,
    }.get(column)


@router.post("/compare", response_model=CompareResponse)
def compare(payload: CompareRequest, db: DbSession, user: CurrentUser) -> CompareResponse:
    products = list(db.scalars(
        select(Product).where(Product.id.in_(payload.product_ids))
    ))
    if not products:
        raise ProductNotFound("None of the supplied product ids exist.")

    # Keep the caller's order: they chose it, and the table columns follow it.
    order = {pid: i for i, pid in enumerate(payload.product_ids)}
    products.sort(key=lambda p: order.get(p.id, 99))

    spec = RequirementSpec()
    ctx = ScoringContext(tags=set())
    context: dict = {}

    if payload.requirement_id:
        requirement = db.get(Requirement, payload.requirement_id)
        if requirement is None:
            raise RequirementNotFound(f"No requirement with id {payload.requirement_id}.")
        plan = plan_service.get_plan(db, requirement.plan_id)
        context = dict(plan.context or {})
        spec = to_spec(requirement)
        ctx = build_scoring_context(context, user.preferences)
    elif payload.plan_id:
        plan = plan_service.get_plan(db, payload.plan_id)
        context = dict(plan.context or {})
        ctx = build_scoring_context(context, user.preferences)
        ctx.tags = derive_context_tags(context)

    rows: list[CompareRow] = []
    for product in products:
        breakdown = score_product(product, spec, ctx)
        rows.append(CompareRow(
            product=product_out(product),
            match_score=round(breakdown["final"], 4),
            deal_value=round(breakdown.get("deal_value", 0.0), 4),
            score_breakdown=ScoreBreakdown(**breakdown),
            is_best={},
        ))

    # Per-column winners, computed here so the table needs no client logic.
    for column in COMPARE_COLUMNS:
        values = [(row, _column_value(row, column)) for row in rows]
        values = [(row, value) for row, value in values if value is not None]
        if not values:
            continue
        best = min(values, key=lambda rv: rv[1]) if column in LOWER_IS_BETTER \
            else max(values, key=lambda rv: rv[1])
        for row, value in values:
            row.is_best[column] = value == best[1]

    winner = {
        "best_overall": max(rows, key=lambda r: r.match_score).product.id,
        "best_budget": min(rows, key=lambda r: r.product.price).product.id,
        "best_rated": max(rows, key=lambda r: (r.product.rating,
                                               r.product.review_count)).product.id,
        "best_premium": max(rows, key=lambda r: r.product.price).product.id,
        "best_deal": max(rows, key=lambda r: r.deal_value).product.id,
    }

    return CompareResponse(columns=list(COMPARE_COLUMNS), rows=rows, winner=winner)


@router.post("/substitute", response_model=SubstituteResponse)
def substitute(payload: SubstituteRequest, db: DbSession,
               user: CurrentUser) -> SubstituteResponse:
    requirement = db.get(Requirement, payload.requirement_id)
    if requirement is None:
        raise RequirementNotFound(f"No requirement with id {payload.requirement_id}.")

    plan = plan_service.get_plan(db, payload.plan_id)
    context = dict(plan.context or {})
    ctx = build_scoring_context(context, user.preferences)

    alternatives = find_substitutes(
        db, requirement, context, ctx,
        current_product_id=payload.current_product_id,
        reason=payload.reason,
        limit=payload.limit,
    )

    return SubstituteResponse(
        requirement_id=requirement.id,
        current_product_id=payload.current_product_id,
        alternatives=[
            AlternativeOut(
                product=product_out(alt["candidate"].product),
                score=round(alt["candidate"].score, 4),
                price_delta=alt["price_delta"],
                score_delta=alt["score_delta"],
                why=alt["why"],
            )
            for alt in alternatives
        ],
    )
