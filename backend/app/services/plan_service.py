"""Plan lifecycle: generate, persist, re-optimize, select.

This is the only place that writes a ShoppingPlan and its children. Both the
agent orchestrator and the REST routers go through here, so a plan created by
chat and a plan created by an API call are byte-identical.

The plan row freezes the context it was generated from. Editing a slot
afterwards marks the plan stale rather than silently changing history --
reproducibility is what makes the recommendations defensible.

Owner: Member 4 (Optimization) with Member 3 (ML).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from dataclasses import field as dc_field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.constants import (
    BundlePreset,
    FulfillmentStatus,
    PlanStatus,
    Priority,
)
from app.core.errors import PlanNotFound
from app.models.plan import Requirement, ShoppingPlan
from app.models.recommendation import BundleItem, PlanBundle, Recommendation, Substitution
from app.models.user import User
from app.services.bundle_optimizer import (
    BundleResult,
    optimize_presets,
    requirement_coverage,
)
from app.services.product_search import get_search_service
from app.services.recommendation import (
    assign_badges,
    build_scoring_context,
    candidate_builder,
    default_presets,
    rank_requirement,
)
from app.services.requirement_planner import (
    adhoc_requirement,
    plan_requirements,
    unmatched_existing_items,
)

log = logging.getLogger("smartbuy.plan")

# How many scored alternatives we keep per requirement for the compare view.
RECOMMENDATIONS_PER_REQUIREMENT = 6


@dataclass
class PlanCreation:
    plan: ShoppingPlan
    assumptions: list[dict] = dc_field(default_factory=list)
    # Things the user said they own that no requirement claimed. Surfaced so
    # we never silently ignore what they told us.
    unmatched_existing: list[str] = dc_field(default_factory=list)
    goal_resolved: bool = True


def _to_requirement_row(plan_id: str, planned) -> Requirement:
    return Requirement(
        plan_id=plan_id,
        kb_item_key=planned.kb_item_key,
        item_name=planned.item_name,
        category=planned.category,
        subcategory=planned.subcategory or "",
        priority=planned.priority,
        quantity=planned.quantity,
        reason=planned.reason,
        est_price_min=planned.est_price_min,
        est_price_max=planned.est_price_max,
        search_terms=list(planned.search_terms or []),
        required_features=list(planned.required_features or []),
        preferred_features=list(planned.preferred_features or []),
        is_owned=planned.is_owned,
        owned_matched_from=planned.owned_matched_from,
        fulfillment_status=(
            FulfillmentStatus.OWNED if planned.is_owned else FulfillmentStatus.PENDING
        ),
    )


def create_plan(
    db: Session,
    *,
    slots: dict,
    user: User | None = None,
    session_id: str | None = None,
    goal_summary: str = "",
) -> PlanCreation:
    """Goal + context -> a persisted plan with requirements, ranked products
    and three bundles."""
    goal_text = str(slots.get("goal_text") or "")
    existing = list(slots.get("existing_items") or [])

    planned = plan_requirements(
        goal_key=slots.get("activity"),
        context=slots,
        existing_items=existing,
        goal_text=goal_text,
    )

    plan = ShoppingPlan(
        user_id=user.id if user else None,
        session_id=session_id,
        goal=goal_text or (planned.goal.display_name if planned.goal else "Shopping plan"),
        goal_summary=goal_summary,
        goal_key=planned.goal_key,
        budget_total=planned.context.get("budget_total"),
        currency=str(slots.get("currency") or "INR"),
        # The frozen copy: inferred season/region included, so the plan can be
        # re-explained later without re-running inference.
        context=_json_safe(planned.context),
        status=PlanStatus.DRAFT,
    )
    db.add(plan)
    db.flush()

    rows = [_to_requirement_row(plan.id, p) for p in planned.requirements]
    db.add_all(rows)
    db.flush()

    optimize_plan(db, plan, user=user, requirements=rows)

    return PlanCreation(
        plan=plan,
        assumptions=[{"slot": a.slot, "value": a.value, "basis": a.basis}
                     for a in planned.assumptions],
        unmatched_existing=unmatched_existing_items(planned, existing),
        goal_resolved=planned.goal is not None,
    )


def create_search_plan(
    db: Session,
    *,
    query: str,
    price_max: int | None = None,
    user: User | None = None,
    session_id: str | None = None,
) -> PlanCreation:
    """Mode A: one named product, run through the full Mode B machinery.

    The result is a plan with exactly one requirement, which means the compare
    view, badges, score breakdowns and explanations all work unchanged.
    """
    requirement = adhoc_requirement(query, price_max)

    # No KB entry means no category to filter on, so ask the index which
    # shelf this query belongs to.
    category, subcategory = get_search_service().infer_taxonomy(
        db, " ".join(requirement.search_terms) or query
    )
    requirement.category = requirement.category or category
    requirement.subcategory = subcategory

    context = {
        "goal_text": query,
        "budget_total": price_max,
        "activity": None,
    }

    plan = ShoppingPlan(
        user_id=user.id if user else None,
        session_id=session_id,
        goal=query[:500],
        goal_key=None,
        budget_total=price_max,
        context=_json_safe(context),
        status=PlanStatus.DRAFT,
    )
    db.add(plan)
    db.flush()

    row = _to_requirement_row(plan.id, requirement)
    db.add(row)
    db.flush()

    # One product needs one basket. Three presets over a single requirement
    # would just be the same item three times.
    optimize_plan(db, plan, user=user, requirements=[row],
                  presets=[BundlePreset.BEST_OVERALL])
    return PlanCreation(plan=plan)


def optimize_plan(
    db: Session,
    plan: ShoppingPlan,
    *,
    user: User | None = None,
    requirements: list[Requirement] | None = None,
    presets: list[str] | None = None,
) -> list[BundleResult]:
    """Score every requirement and rebuild all bundles for a plan.

    Safe to re-run: existing recommendations, bundles and substitutions are
    replaced, never appended to.
    """
    rows = requirements if requirements is not None else list(plan.requirements)
    to_buy = [r for r in rows if not r.is_owned]

    context = dict(plan.context or {})
    preferences = user.preferences if user is not None else None
    scoring_ctx = build_scoring_context(context, preferences)

    _clear_derived(db, plan.id)

    if not to_buy:
        plan.status = PlanStatus.COMPLETE
        plan.estimated_total = 0
        plan.estimated_savings = 0
        db.flush()
        return []

    builder = candidate_builder(db, to_buy, context, scoring_ctx)
    presets = presets or default_presets()
    results = optimize_presets(builder, plan.budget_total, presets=presets)

    # Recommendations are shown alongside whichever bundle is selected, so
    # they use that preset's scores.
    default_preset = BundlePreset.BEST_OVERALL if BundlePreset.BEST_OVERALL in presets \
        else presets[0]
    _persist_recommendations(db, plan, to_buy, builder(default_preset))
    selected = _persist_bundles(db, plan, results, rows, default_preset)

    if selected is not None:
        plan.estimated_total = selected.total_cost
        plan.estimated_savings = selected.total_savings
        plan.status = (
            PlanStatus.BUDGET_INFEASIBLE if selected.infeasible else PlanStatus.COMPLETE
        )
        _persist_substitutions(db, plan, selected)
        _mark_fulfillment(db, rows, selected)

    plan.is_stale = False
    db.flush()
    return results


def _clear_derived(db: Session, plan_id: str) -> None:
    """Drop everything downstream of the requirement list.

    ORM-level deletes rather than bulk SQL: cascades then behave identically
    on SQLite and Postgres, which is the whole point of ADR-004.
    """
    bundle_ids = db.scalars(
        select(PlanBundle.id).where(PlanBundle.plan_id == plan_id)
    ).all()
    if bundle_ids:
        for item in db.scalars(
            select(BundleItem).where(BundleItem.bundle_id.in_(bundle_ids))
        ).all():
            db.delete(item)

    for model in (PlanBundle, Recommendation, Substitution):
        for row in db.scalars(select(model).where(model.plan_id == plan_id)).all():
            db.delete(row)
    db.flush()


def _persist_recommendations(db: Session, plan: ShoppingPlan,
                             requirements: list[Requirement], candidate_sets) -> None:
    """Keep the top N scored products per requirement, with comparison badges."""
    by_key = {rc.key: rc for rc in candidate_sets}

    for requirement in requirements:
        rc = by_key.get(requirement.id)
        if rc is None or not rc.candidates:
            requirement.fulfillment_status = FulfillmentStatus.UNFULFILLED
            requirement.unfulfilled_reason = "no_candidates"
            continue

        top = rc.candidates[:RECOMMENDATIONS_PER_REQUIREMENT]
        badges = assign_badges(top)

        for rank, candidate in enumerate(top, start=1):
            db.add(Recommendation(
                plan_id=plan.id,
                requirement_id=requirement.id,
                product_id=candidate.product.id,
                score=round(float(candidate.score), 4),
                rank=rank,
                badge=badges.get(candidate.product.id),
                score_breakdown={k: round(float(v), 4)
                                 for k, v in (candidate.breakdown or {}).items()},
                reasons=list(candidate.reasons or []),
            ))
    db.flush()


def _persist_bundles(db: Session, plan: ShoppingPlan, results: list[BundleResult],
                     all_requirements: list[Requirement],
                     default_preset: str = BundlePreset.BEST_OVERALL) -> BundleResult | None:
    """Write one PlanBundle per preset. best_overall is selected by default."""
    selected: BundleResult | None = None

    for result in results:
        bundle = PlanBundle(
            plan_id=plan.id,
            preset=result.preset,
            total_cost=result.total_cost,
            total_savings=result.total_savings,
            remaining_budget=result.remaining_budget,
            utility_score=result.utility_score,
            requirement_coverage=requirement_coverage(result, all_requirements),
            is_selected=(result.preset == default_preset),
            excluded=list(result.excluded or []),
        )
        db.add(bundle)
        db.flush()

        for item in result.items:
            db.add(BundleItem(
                bundle_id=bundle.id,
                requirement_id=item.requirement.id,
                product_id=item.candidate.product.id,
                quantity=item.quantity,
                line_total=item.line_total,
                score=round(float(item.candidate.score), 4),
                reasons=list(item.candidate.reasons or []),
            ))

        if bundle.is_selected:
            selected = result

    db.flush()
    return selected or (results[0] if results else None)


def _persist_substitutions(db: Session, plan: ShoppingPlan, result: BundleResult) -> None:
    for sub in result.substitutions:
        db.add(Substitution(
            plan_id=plan.id,
            requirement_id=sub.requirement.id,
            from_product_id=sub.from_candidate.product.id,
            to_product_id=sub.to_candidate.product.id,
            price_delta=sub.price_delta,
            score_delta=sub.score_delta,
            reason=sub.reason,
        ))
    db.flush()


def _mark_fulfillment(db: Session, requirements: list[Requirement],
                      selected: BundleResult) -> None:
    """Record what the selected bundle actually covers, and why not otherwise."""
    covered = {item.requirement.id for item in selected.items}
    excluded_reason = {e.get("requirement_id"): e.get("reason")
                       for e in (selected.excluded or [])}

    for requirement in requirements:
        if requirement.is_owned:
            requirement.fulfillment_status = FulfillmentStatus.OWNED
            requirement.unfulfilled_reason = None
        elif requirement.id in covered:
            requirement.fulfillment_status = FulfillmentStatus.FULFILLED
            requirement.unfulfilled_reason = None
        else:
            requirement.fulfillment_status = FulfillmentStatus.UNFULFILLED
            requirement.unfulfilled_reason = excluded_reason.get(requirement.id, "over_budget")
    db.flush()


# --------------------------------------------------------------------------
# Reads and mutations used by the routers
# --------------------------------------------------------------------------
def get_plan(db: Session, plan_id: str) -> ShoppingPlan:
    plan = db.scalars(
        select(ShoppingPlan)
        .where(ShoppingPlan.id == plan_id)
        .options(
            selectinload(ShoppingPlan.requirements),
            selectinload(ShoppingPlan.bundles).selectinload(PlanBundle.items),
        )
    ).first()
    if plan is None:
        raise PlanNotFound(f"No plan with id {plan_id}.")
    return plan


def select_bundle(db: Session, plan: ShoppingPlan, preset: str) -> PlanBundle:
    target: PlanBundle | None = None
    for bundle in plan.bundles:
        bundle.is_selected = bundle.preset == preset
        if bundle.is_selected:
            target = bundle
    if target is None:
        raise PlanNotFound(f"Plan has no '{preset}' bundle.")

    plan.estimated_total = target.total_cost
    plan.estimated_savings = target.total_savings
    db.flush()
    return target


def selected_bundle(plan: ShoppingPlan) -> PlanBundle | None:
    for bundle in plan.bundles:
        if bundle.is_selected:
            return bundle
    return plan.bundles[0] if plan.bundles else None


def set_requirement_owned(db: Session, plan: ShoppingPlan, requirement_id: str,
                          is_owned: bool, user: User | None = None) -> ShoppingPlan:
    """Tick or untick "I already have this", then re-optimize.

    Freeing an essential item's budget genuinely changes the whole basket, so
    a full re-run is the correct behaviour, not an optimization.
    """
    requirement = next((r for r in plan.requirements if r.id == requirement_id), None)
    if requirement is None:
        raise PlanNotFound(f"Requirement {requirement_id} is not part of this plan.")

    requirement.is_owned = is_owned
    requirement.fulfillment_status = (
        FulfillmentStatus.OWNED if is_owned else FulfillmentStatus.PENDING
    )
    if not is_owned:
        requirement.owned_matched_from = None
    db.flush()

    optimize_plan(db, plan, user=user)
    return plan


def update_budget(db: Session, plan: ShoppingPlan, budget_total: int | None,
                  user: User | None = None) -> ShoppingPlan:
    plan.budget_total = budget_total
    context = dict(plan.context or {})
    context["budget_total"] = budget_total
    plan.context = context
    db.flush()
    optimize_plan(db, plan, user=user)
    return plan


def plan_estimate(plan: ShoppingPlan) -> dict:
    """Pre-optimization estimate straight from the KB price bands."""
    to_buy = [r for r in plan.requirements if not r.is_owned]
    return {
        "min": sum(r.est_price_min * r.quantity for r in to_buy),
        "max": sum(r.est_price_max * r.quantity for r in to_buy),
        "items": len(to_buy),
        "essentials": sum(1 for r in to_buy if r.priority == Priority.ESSENTIAL),
    }


def top_recommendation(db: Session, plan_id: str, requirement_id: str) -> Recommendation | None:
    return db.scalars(
        select(Recommendation)
        .where(Recommendation.plan_id == plan_id,
               Recommendation.requirement_id == requirement_id)
        .order_by(Recommendation.rank)
    ).first()


def rank_for_requirement(db: Session, plan: ShoppingPlan, requirement: Requirement,
                         user: User | None = None, preset: str | None = None,
                         limit: int = 40):
    """Fresh ranking for one requirement -- used by compare and substitution."""
    context = dict(plan.context or {})
    scoring_ctx = build_scoring_context(context, user.preferences if user else None)
    return rank_requirement(db, requirement, context, scoring_ctx, preset=preset, limit=limit)


def _json_safe(value):
    """SQLite's JSON column will not accept sets or dataclasses."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
