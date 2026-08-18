"""Plan, requirement and bundle response schemas.

Mirrors docs/API_CONTRACT.md sections 2, 5 and 6. Shapes are chosen so the
frontend renders them without transformation -- requirements arrive already
grouped by priority, bundles already carry their totals.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.product import ProductOut


class RequirementOut(ORMModel):
    id: str
    kb_item_key: str | None = None
    item_name: str
    category: str
    subcategory: str = ""
    priority: str
    quantity: int = 1
    reason: str = ""
    est_price_min: int = 0
    est_price_max: int = 0
    required_features: list[str] = Field(default_factory=list)
    preferred_features: list[str] = Field(default_factory=list)
    is_owned: bool = False
    fulfillment_status: str = "pending"
    unfulfilled_reason: str | None = None


class RequirementGroups(BaseModel):
    essential: list[RequirementOut] = Field(default_factory=list)
    recommended: list[RequirementOut] = Field(default_factory=list)
    optional: list[RequirementOut] = Field(default_factory=list)


class OwnedItem(BaseModel):
    item_name: str
    matched_from: str | None = None


class EstimatedRange(BaseModel):
    min: int = 0
    max: int = 0


class RequirementsResponse(BaseModel):
    plan_id: str
    goal: str
    goal_summary: str = ""
    context: dict = Field(default_factory=dict)
    requirements: RequirementGroups
    already_owned: list[OwnedItem] = Field(default_factory=list)
    estimated_range: EstimatedRange


class GenerateRequirementsRequest(BaseModel):
    session_id: str


class RequirementPatch(BaseModel):
    is_owned: bool | None = None
    quantity: int | None = Field(default=None, ge=1, le=20)


# --------------------------------------------------------------------------
# Bundles
# --------------------------------------------------------------------------
class BundleItemOut(BaseModel):
    requirement: RequirementOut
    product: ProductOut
    quantity: int = 1
    line_total: int = 0
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class ExcludedOut(BaseModel):
    requirement_id: str | None = None
    item_name: str = ""
    reason: str = ""
    detail: str = ""


class BundleOut(BaseModel):
    preset: str
    total_cost: int = 0
    total_savings: int = 0
    remaining_budget: int = 0
    # Non-zero only when a preset deliberately overshoots the stated budget.
    over_budget: int = 0
    utility_score: float = 0.0
    requirement_coverage: float = 0.0
    is_selected: bool = False
    items: list[BundleItemOut] = Field(default_factory=list)
    excluded: list[ExcludedOut] = Field(default_factory=list)


class SubstitutionOut(BaseModel):
    requirement_id: str
    item_name: str = ""
    from_product: ProductOut | None = Field(default=None, alias="from")
    to_product: ProductOut | None = Field(default=None, alias="to")
    price_delta: int = 0
    score_delta: float = 0.0
    reason: str = ""

    model_config = {"populate_by_name": True}


class UnfulfilledOut(BaseModel):
    requirement_id: str
    item_name: str
    reason: str


class PlanTotals(BaseModel):
    budget: int | None = None
    estimated_total: int = 0
    savings: int = 0
    remaining: int = 0
    over_budget: int = 0


class ShoppingPlanResponse(BaseModel):
    plan_id: str
    goal: str
    goal_summary: str = ""
    status: str
    is_stale: bool = False
    context: dict = Field(default_factory=dict)
    requirements: RequirementGroups
    already_owned: list[OwnedItem] = Field(default_factory=list)
    bundles: list[BundleOut] = Field(default_factory=list)
    selected_preset: str | None = None
    totals: PlanTotals
    substitutions: list[SubstitutionOut] = Field(default_factory=list)
    unfulfilled: list[UnfulfilledOut] = Field(default_factory=list)


class BundleOptimizeRequest(BaseModel):
    plan_id: str
    presets: list[str] | None = None
    include_priorities: list[str] | None = None


class BundleOptimizeResponse(BaseModel):
    plan_id: str
    budget: int | None = None
    bundles: list[BundleOut] = Field(default_factory=list)
    substitutions: list[SubstitutionOut] = Field(default_factory=list)
    infeasible: bool = False
    shortfall: int | None = None


class BundleSelectRequest(BaseModel):
    plan_id: str
    preset: str
