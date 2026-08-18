"""Shared response objects. These mirror docs/API_CONTRACT.md exactly."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ScoreBreakdown(BaseModel):
    """The eight weighted components behind every match score.

    Never omitted from a recommendation: the explanation layer is grounded in
    these numbers, and Page 7 renders them directly.
    """

    goal_suitability: float = 0.0
    preference_match: float = 0.0
    quality: float = 0.0
    feature_match: float = 0.0
    budget_fit: float = 0.0
    review_strength: float = 0.0
    delivery: float = 0.0
    deal_value: float = 0.0
    final: float = 0.0


class WeightedPoint(BaseModel):
    """One row of the Page 7 scorecard. Across all rows, `max` sums to 100."""

    label: str
    earned: float
    max: float


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail
