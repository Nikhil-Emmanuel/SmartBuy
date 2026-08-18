"""Admin metrics and audit log. API contract section 7.

Every number below is a real aggregate query. There are no hard-coded demo
values here -- a dashboard that lies is worse than no dashboard, and this one
is shown on stage.

Protected by X-Admin-Token.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminOnly, DbSession
from app.models.audit import AuditLog
from app.models.feedback import Feedback
from app.models.plan import Requirement, ShoppingPlan
from app.models.product import Product
from app.models.recommendation import PlanBundle, Recommendation
from app.models.session import ChatSession
from app.models.user import User
from app.schemas.feedback import (
    AuditLogOut,
    AuditLogsResponse,
    CategoryCount,
    LLMMetrics,
    MetricsResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

POSITIVE_FEEDBACK = ("relevant", "saved")


@router.get("/metrics", response_model=MetricsResponse)
def metrics(db: DbSession, _: AdminOnly) -> MetricsResponse:
    def count(model) -> int:
        return int(db.scalar(select(func.count()).select_from(model)) or 0)

    selected = select(PlanBundle).where(PlanBundle.is_selected.is_(True)).subquery()

    avg_bundle_value = int(db.scalar(
        select(func.avg(selected.c.total_cost))
    ) or 0)

    coverage_avg = float(db.scalar(
        select(func.avg(selected.c.requirement_coverage))
    ) or 0.0)

    # Budget compliance: of the plans that stated a budget, how many ended up
    # within it.
    with_budget = db.execute(
        select(ShoppingPlan.budget_total, selected.c.total_cost)
        .join(selected, selected.c.plan_id == ShoppingPlan.id)
        .where(ShoppingPlan.budget_total.isnot(None))
    ).all()
    compliant = sum(1 for budget, cost in with_budget if cost <= budget)
    compliance_rate = round(compliant / len(with_budget), 4) if with_budget else 0.0

    feedback_counts = {
        row[0]: int(row[1]) for row in db.execute(
            select(Feedback.feedback_type, func.count())
            .group_by(Feedback.feedback_type)
        ).all()
    }
    total_feedback = sum(feedback_counts.values())
    positive = sum(feedback_counts.get(k, 0) for k in POSITIVE_FEEDBACK)
    acceptance = round(positive / total_feedback, 4) if total_feedback else 0.0

    llm_rows = db.execute(
        select(AuditLog.status, func.count(), func.avg(AuditLog.latency_ms))
        .where(AuditLog.action == "llm_call")
        .group_by(AuditLog.status)
    ).all()
    llm_calls = sum(int(r[1]) for r in llm_rows)
    llm_failures = sum(int(r[1]) for r in llm_rows if r[0] in ("fallback", "error"))
    weighted_latency = sum(int(r[1]) * float(r[2] or 0) for r in llm_rows)

    top_categories = [
        CategoryCount(category=row[0], count=int(row[1]))
        for row in db.execute(
            select(Requirement.category, func.count())
            .group_by(Requirement.category)
            .order_by(func.count().desc())
            .limit(10)
        ).all()
    ]

    return MetricsResponse(
        users=count(User),
        sessions=count(ChatSession),
        plans_generated=count(ShoppingPlan),
        recommendations_generated=count(Recommendation),
        avg_bundle_value=avg_bundle_value,
        budget_compliance_rate=compliance_rate,
        requirement_coverage_avg=round(coverage_avg, 4),
        feedback=feedback_counts,
        recommendation_acceptance_rate=acceptance,
        llm=LLMMetrics(
            calls=llm_calls,
            failures=llm_failures,
            fallback_rate=round(llm_failures / llm_calls, 4) if llm_calls else 0.0,
            avg_latency_ms=int(weighted_latency / llm_calls) if llm_calls else 0,
        ),
        top_categories=top_categories,
        catalog_size=count(Product),
    )


@router.get("/audit-logs", response_model=AuditLogsResponse)
def audit_logs(
    db: DbSession,
    _: AdminOnly,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session_id: str | None = None,
    action: str | None = None,
    status: str | None = None,
) -> AuditLogsResponse:
    query = select(AuditLog)
    counter = select(func.count()).select_from(AuditLog)

    for column, value in (
        (AuditLog.session_id, session_id),
        (AuditLog.action, action),
        (AuditLog.status, status),
    ):
        if value:
            query = query.where(column == value)
            counter = counter.where(column == value)

    rows = db.scalars(
        query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return AuditLogsResponse(
        logs=[AuditLogOut.model_validate(r, from_attributes=True) for r in rows],
        total=int(db.scalar(counter) or 0),
    )
