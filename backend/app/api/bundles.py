"""Bundle optimization and the full plan payload. API contract sections 5 and 6.

Wave 4 -- Page 6 is the money shot of the demo, and it is served entirely by
`GET /api/shopping-plan/{plan_id}` in a single round trip.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.serializers import bundle_out, plan_response, substitution_out
from app.core.constants import BundlePreset, PlanStatus
from app.core.errors import ValidationError
from app.schemas.plan import (
    BundleOptimizeRequest,
    BundleOptimizeResponse,
    BundleSelectRequest,
    ShoppingPlanResponse,
)
from app.services import plan_service

router = APIRouter(prefix="/api", tags=["bundles"])

VALID_PRESETS = {p.value for p in BundlePreset}


@router.post("/bundle/optimize", response_model=BundleOptimizeResponse)
def optimize(payload: BundleOptimizeRequest, db: DbSession,
             user: CurrentUser) -> BundleOptimizeResponse:
    """Re-run the optimizer.

    An infeasible budget is a 200, not an error: the response says so honestly
    and still returns the essentials-only bundle, because a user who cannot
    afford everything still needs to know what to buy first.
    """
    plan = plan_service.get_plan(db, payload.plan_id)

    presets = payload.presets or None
    if presets:
        unknown = [p for p in presets if p not in VALID_PRESETS]
        if unknown:
            raise ValidationError(f"Unknown bundle preset(s): {', '.join(unknown)}.")

    plan_service.optimize_plan(db, plan, user=user, presets=presets)
    db.commit()
    db.refresh(plan)

    requirements = {r.id: r for r in plan.requirements}
    bundles = sorted(plan.bundles, key=lambda b: b.total_cost)
    selected = next((b for b in plan.bundles if b.is_selected), None)

    return BundleOptimizeResponse(
        plan_id=plan.id,
        budget=plan.budget_total,
        bundles=[bundle_out(b, plan.budget_total) for b in bundles],
        substitutions=[substitution_out(s, requirements) for s in plan.substitutions],
        infeasible=plan.status == PlanStatus.BUDGET_INFEASIBLE,
        shortfall=_shortfall(plan, selected),
    )


def _shortfall(plan, selected) -> int | None:
    """How far short the budget falls, when it does. Never fabricated."""
    if plan.status != PlanStatus.BUDGET_INFEASIBLE or not plan.budget_total:
        return None
    missing = [r for r in plan.requirements
               if not r.is_owned and r.priority == "essential"
               and r.fulfillment_status == "unfulfilled"]
    # Cheapest honest estimate of what is still needed, from the KB bands.
    return sum(r.est_price_min * r.quantity for r in missing) or None


@router.post("/bundle/select", response_model=ShoppingPlanResponse)
def select(payload: BundleSelectRequest, db: DbSession) -> ShoppingPlanResponse:
    if payload.preset not in VALID_PRESETS:
        raise ValidationError(f"Unknown bundle preset '{payload.preset}'.")

    plan = plan_service.get_plan(db, payload.plan_id)
    plan_service.select_bundle(db, plan, payload.preset)
    db.commit()
    db.refresh(plan)
    return plan_response(plan)


@router.get("/shopping-plan/{plan_id}", response_model=ShoppingPlanResponse)
def get_shopping_plan(plan_id: str, db: DbSession) -> ShoppingPlanResponse:
    return plan_response(plan_service.get_plan(db, plan_id))
