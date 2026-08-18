"""ORM -> response-schema conversion.

Kept out of the routers so that a plan serialised by `/api/shopping-plan/{id}`
is byte-identical to one serialised by `/api/bundle/optimize`. Any drift here
shows up as a frontend bug that looks like a backend bug.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.constants import PRIORITY_ORDER, Priority
from app.models.plan import Requirement, ShoppingPlan
from app.models.product import Offer, Product
from app.models.recommendation import PlanBundle, Recommendation, Substitution
from app.schemas.common import ScoreBreakdown
from app.schemas.plan import (
    BundleItemOut,
    BundleOut,
    EstimatedRange,
    ExcludedOut,
    OwnedItem,
    PlanTotals,
    RequirementGroups,
    RequirementOut,
    RequirementsResponse,
    ShoppingPlanResponse,
    SubstitutionOut,
    UnfulfilledOut,
)
from app.schemas.product import OfferOut, ProductOut
from app.schemas.recommendation import RecommendationOut


def product_out(product: Product) -> ProductOut:
    return ProductOut.from_model(product)


def requirement_out(requirement: Requirement) -> RequirementOut:
    return RequirementOut.model_validate(requirement)


def group_requirements(requirements: list[Requirement]) -> RequirementGroups:
    """Grouped by priority, each group ordered as the planner ordered it."""
    ordered = sorted(
        requirements,
        key=lambda r: (PRIORITY_ORDER.get(r.priority, 9), r.item_name),
    )
    return RequirementGroups(
        essential=[requirement_out(r) for r in ordered if r.priority == Priority.ESSENTIAL],
        recommended=[requirement_out(r) for r in ordered
                     if r.priority == Priority.RECOMMENDED],
        optional=[requirement_out(r) for r in ordered if r.priority == Priority.OPTIONAL],
    )


def owned_items(requirements: list[Requirement]) -> list[OwnedItem]:
    return [
        OwnedItem(item_name=r.item_name, matched_from=r.owned_matched_from)
        for r in requirements if r.is_owned
    ]


def estimated_range(plan: ShoppingPlan) -> EstimatedRange:
    """What this plan will actually cost.

    Once bundles exist we quote the real spread between the cheapest and the
    most expensive basket, because those are prices from the catalog. The
    knowledge-base bands are only a fallback for a plan that has not been
    optimized yet -- they are deliberately wide, and showing "Rs 20,900 to
    Rs 70,700" one screen before "Rs 13,404" makes the plan look wrong.
    """
    costs = [b.total_cost for b in plan.bundles if b.total_cost > 0]
    if costs:
        return EstimatedRange(min=min(costs), max=max(costs))

    to_buy = [r for r in plan.requirements if not r.is_owned]
    return EstimatedRange(
        min=sum(r.est_price_min * r.quantity for r in to_buy),
        max=sum(r.est_price_max * r.quantity for r in to_buy),
    )


def best_offer(db: Session, product_id: str) -> OfferOut | None:
    offer = db.query(Offer).filter(Offer.product_id == product_id).first()
    return OfferOut.model_validate(offer) if offer else None


def recommendation_out(rec: Recommendation, offer: OfferOut | None = None) -> RecommendationOut:
    return RecommendationOut(
        product=product_out(rec.product),
        requirement_id=rec.requirement_id,
        score=rec.score,
        rank=rec.rank,
        badge=rec.badge,
        score_breakdown=ScoreBreakdown(**(rec.score_breakdown or {})),
        reasons=list(rec.reasons or []),
        offer=offer,
    )


def bundle_out(bundle: PlanBundle, budget: int | None = None) -> BundleOut:
    items = sorted(
        bundle.items,
        key=lambda i: (PRIORITY_ORDER.get(i.requirement.priority, 9),
                       i.requirement.item_name),
    )
    over = max(0, bundle.total_cost - budget) if budget else 0
    return BundleOut(
        preset=bundle.preset,
        total_cost=bundle.total_cost,
        total_savings=bundle.total_savings,
        remaining_budget=bundle.remaining_budget,
        over_budget=over,
        utility_score=bundle.utility_score,
        requirement_coverage=bundle.requirement_coverage,
        is_selected=bundle.is_selected,
        items=[
            BundleItemOut(
                requirement=requirement_out(item.requirement),
                product=product_out(item.product),
                quantity=item.quantity,
                line_total=item.line_total,
                score=item.score,
                reasons=list(item.reasons or []),
            )
            for item in items
        ],
        excluded=[ExcludedOut(**e) for e in (bundle.excluded or [])],
    )


def substitution_out(sub: Substitution, requirements: dict[str, Requirement]) -> SubstitutionOut:
    requirement = requirements.get(sub.requirement_id)
    return SubstitutionOut(
        requirement_id=sub.requirement_id,
        item_name=requirement.item_name if requirement else "",
        **{
            "from": product_out(sub.from_product) if sub.from_product else None,
            "to": product_out(sub.to_product) if sub.to_product else None,
        },
        price_delta=sub.price_delta,
        score_delta=sub.score_delta,
        reason=sub.reason,
    )


def unfulfilled(requirements: list[Requirement]) -> list[UnfulfilledOut]:
    """Gaps the user needs to know about.

    An optional item the optimizer skipped to protect the budget is not a
    gap -- it is the optimizer working, and it is already listed under the
    bundle's `excluded`. Only unmet essentials, and anything we simply could
    not find a product for, belong here.
    """
    return [
        UnfulfilledOut(
            requirement_id=r.id,
            item_name=r.item_name,
            reason=r.unfulfilled_reason or "over_budget",
        )
        for r in requirements
        if not r.is_owned and r.fulfillment_status == "unfulfilled"
        and (r.priority == Priority.ESSENTIAL or r.unfulfilled_reason == "no_candidates")
    ]


def requirements_response(plan: ShoppingPlan) -> RequirementsResponse:
    requirements = list(plan.requirements)
    return RequirementsResponse(
        plan_id=plan.id,
        goal=plan.goal,
        goal_summary=plan.goal_summary or "",
        context=dict(plan.context or {}),
        requirements=group_requirements(requirements),
        already_owned=owned_items(requirements),
        estimated_range=estimated_range(plan),
    )


def plan_response(plan: ShoppingPlan) -> ShoppingPlanResponse:
    """The Page 6 payload: everything the plan screen needs in one call."""
    requirements = list(plan.requirements)
    by_id = {r.id: r for r in requirements}
    bundles = sorted(plan.bundles, key=lambda b: b.total_cost)
    selected = next((b for b in plan.bundles if b.is_selected),
                    bundles[0] if bundles else None)

    totals = PlanTotals(
        budget=plan.budget_total,
        estimated_total=selected.total_cost if selected else 0,
        savings=selected.total_savings if selected else 0,
        remaining=selected.remaining_budget if selected else 0,
        over_budget=(max(0, selected.total_cost - plan.budget_total)
                     if selected and plan.budget_total else 0),
    )

    return ShoppingPlanResponse(
        plan_id=plan.id,
        goal=plan.goal,
        goal_summary=plan.goal_summary or "",
        status=plan.status,
        is_stale=plan.is_stale,
        context=dict(plan.context or {}),
        requirements=group_requirements(requirements),
        already_owned=owned_items(requirements),
        bundles=[bundle_out(b, plan.budget_total) for b in bundles],
        selected_preset=selected.preset if selected else None,
        totals=totals,
        substitutions=[substitution_out(s, by_id) for s in plan.substitutions],
        unfulfilled=unfulfilled(requirements),
    )
