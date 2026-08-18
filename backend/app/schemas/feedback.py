"""Feedback, profile and admin schemas.

Mirrors docs/API_CONTRACT.md sections 6 and 7.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.product import ProductOut


class FeedbackRequest(BaseModel):
    product_id: str | None = None
    plan_id: str | None = None
    session_id: str | None = None
    feedback_type: str  # relevant | not_relevant | saved | not_interested
    comment: str | None = Field(default=None, max_length=1000)


class PreferencesOut(BaseModel):
    preferred_categories: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    min_price: int | None = None
    max_price: int | None = None
    price_bias: str = "balanced"
    delivery_bias: str = "standard"
    brand_affinity: dict[str, float] = Field(default_factory=dict)
    category_affinity: dict[str, float] = Field(default_factory=dict)
    subcategory_affinity: dict[str, float] = Field(default_factory=dict)


class FeedbackResponse(BaseModel):
    ok: bool = True
    preferences_updated: bool = False
    updated_preferences: PreferencesOut | None = None


class PlanSummaryOut(BaseModel):
    plan_id: str
    goal: str
    status: str
    estimated_total: int = 0
    budget_total: int | None = None
    created_at: datetime | None = None


class FeedbackHistoryOut(BaseModel):
    product: ProductOut | None = None
    feedback_type: str
    created_at: datetime | None = None


class ProfileResponse(BaseModel):
    user_id: str
    is_anonymous: bool = True
    preferences: PreferencesOut
    saved_products: list[ProductOut] = Field(default_factory=list)
    recent_plans: list[PlanSummaryOut] = Field(default_factory=list)
    feedback_history: list[FeedbackHistoryOut] = Field(default_factory=list)


class ProfileUpdateRequest(BaseModel):
    preferred_categories: list[str] | None = None
    preferred_brands: list[str] | None = None
    min_price: int | None = Field(default=None, ge=0, le=10_000_000)
    max_price: int | None = Field(default=None, ge=0, le=10_000_000)
    price_bias: str | None = None
    delivery_bias: str | None = None


class InteractionRequest(BaseModel):
    product_id: str
    interaction_type: str  # viewed | clicked | liked | disliked | saved | purchased


# --------------------------------------------------------------------------
# Admin
# --------------------------------------------------------------------------
class LLMMetrics(BaseModel):
    calls: int = 0
    failures: int = 0
    fallback_rate: float = 0.0
    avg_latency_ms: int = 0


class CategoryCount(BaseModel):
    category: str
    count: int


class MetricsResponse(BaseModel):
    users: int = 0
    sessions: int = 0
    plans_generated: int = 0
    recommendations_generated: int = 0
    avg_bundle_value: int = 0
    budget_compliance_rate: float = 0.0
    requirement_coverage_avg: float = 0.0
    feedback: dict[str, int] = Field(default_factory=dict)
    recommendation_acceptance_rate: float = 0.0
    llm: LLMMetrics = Field(default_factory=LLMMetrics)
    top_categories: list[CategoryCount] = Field(default_factory=list)
    catalog_size: int = 0


class AuditLogOut(BaseModel):
    id: str
    session_id: str | None = None
    action: str
    tool: str | None = None
    input_summary: str = ""
    output_summary: str = ""
    model_version: str | None = None
    latency_ms: int = 0
    status: str = "ok"
    created_at: datetime | None = None


class AuditLogsResponse(BaseModel):
    logs: list[AuditLogOut] = Field(default_factory=list)
    total: int = 0
