"""Recommendation, comparison and explanation schemas.

Mirrors docs/API_CONTRACT.md section 4. Every recommendation carries its full
score breakdown -- there is no score without its components, because the
explanation layer is grounded in them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ScoreBreakdown, WeightedPoint
from app.schemas.plan import RequirementOut
from app.schemas.product import OfferOut, ProductOut


class RecommendationOut(BaseModel):
    product: ProductOut
    requirement_id: str
    score: float = 0.0
    rank: int = 0
    badge: str | None = None
    score_breakdown: ScoreBreakdown
    reasons: list[str] = Field(default_factory=list)
    offer: OfferOut | None = None


class RequirementResults(BaseModel):
    requirement: RequirementOut
    recommendations: list[RecommendationOut] = Field(default_factory=list)
    unfulfilled_reason: str | None = None


class RecommendationsRequest(BaseModel):
    plan_id: str
    requirement_ids: list[str] | None = None
    limit_per_requirement: int = Field(default=5, ge=1, le=20)


class RecommendationsResponse(BaseModel):
    plan_id: str
    results: list[RequirementResults] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------
COMPARE_COLUMNS = [
    "price", "rating", "review_count", "delivery_days",
    "match_score", "deal_value", "availability",
]


class CompareRow(BaseModel):
    product: ProductOut
    match_score: float = 0.0
    deal_value: float = 0.0
    score_breakdown: ScoreBreakdown
    # Per-column "this one wins" flags, so the table needs no client logic.
    is_best: dict[str, bool] = Field(default_factory=dict)


class CompareRequest(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=6)
    plan_id: str | None = None
    requirement_id: str | None = None


class CompareResponse(BaseModel):
    columns: list[str] = Field(default_factory=lambda: list(COMPARE_COLUMNS))
    rows: list[CompareRow] = Field(default_factory=list)
    winner: dict[str, str | None] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Explanation
# --------------------------------------------------------------------------
class ExplainRequest(BaseModel):
    product_id: str
    requirement_id: str | None = None
    plan_id: str | None = None


class ExplainResponse(BaseModel):
    match_score: float
    score_breakdown: ScoreBreakdown
    weighted_points: list[WeightedPoint] = Field(default_factory=list)
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    # False when the prose came from the deterministic layer rather than the
    # model -- either it was unavailable, or its output failed grounding.
    llm_generated: bool = False


# --------------------------------------------------------------------------
# Substitution
# --------------------------------------------------------------------------
class SubstituteRequest(BaseModel):
    plan_id: str
    requirement_id: str
    current_product_id: str
    reason: str = "cheaper"  # cheaper | better_rated | faster_delivery | unavailable
    limit: int = Field(default=5, ge=1, le=10)


class AlternativeOut(BaseModel):
    product: ProductOut
    score: float = 0.0
    price_delta: int = 0
    score_delta: float = 0.0
    why: str = ""


class SubstituteResponse(BaseModel):
    requirement_id: str
    current_product_id: str
    alternatives: list[AlternativeOut] = Field(default_factory=list)
