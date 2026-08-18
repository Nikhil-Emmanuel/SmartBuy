"""Controlled vocabularies and enums.

These strings are a contract between the catalog (Member 2), the requirement
knowledge base (Member 4), and the ranking engine (Member 3). If they drift,
requirements silently match zero products -- the most likely way this project
fails on stage. scripts/validate_vocab.py enforces them.

Stored as plain strings in the DB (not SQLAlchemy Enum) so that SQLite and
Postgres behave identically and no migration is needed to add a value.
"""

from __future__ import annotations

from enum import StrEnum


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------
class Intent(StrEnum):
    GOAL_BASED_SHOPPING = "GOAL_BASED_SHOPPING"
    SPECIFIC_PRODUCT_SEARCH = "SPECIFIC_PRODUCT_SEARCH"
    PRODUCT_COMPARISON = "PRODUCT_COMPARISON"
    FIND_ALTERNATIVE = "FIND_ALTERNATIVE"
    FIND_BEST_DEAL = "FIND_BEST_DEAL"
    BUDGET_OPTIMIZATION = "BUDGET_OPTIMIZATION"
    GENERAL_RECOMMENDATION = "GENERAL_RECOMMENDATION"


class AgentState(StrEnum):
    INTAKE = "INTAKE"
    SLOT_FILL = "SLOT_FILL"
    PLANNING = "PLANNING"
    DISCOVERY = "DISCOVERY"
    OPTIMIZING = "OPTIMIZING"
    PRESENTED = "PRESENTED"
    REFINING = "REFINING"


class NextAction(StrEnum):
    ANSWER_QUESTION = "answer_question"
    VIEW_REQUIREMENTS = "view_requirements"
    VIEW_PLAN = "view_plan"
    NONE = "none"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# --------------------------------------------------------------------------
# Catalog
# --------------------------------------------------------------------------
class Source(StrEnum):
    MARKET_A = "MARKET_A"
    MARKET_B = "MARKET_B"
    MARKET_C = "MARKET_C"


SOURCE_DISPLAY_NAMES: dict[str, str] = {
    "MARKET_A": "Marketplace A",
    "MARKET_B": "Marketplace B",
    "MARKET_C": "Marketplace C",
}


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"


CATEGORIES: tuple[str, ...] = (
    "footwear",
    "clothing",
    "outerwear",
    "equipment",
    "electronics",
    "safety",
    "camping",
    "hydration",
    "navigation",
    "accessories",
    "furniture",
    "kitchen",
    "bedding",
    "storage",
    "personal_care",
)

FEATURES: tuple[str, ...] = (
    "waterproof",
    "water_resistant",
    "windproof",
    "insulated",
    "thermal",
    "breathable",
    "lightweight",
    "quick_dry",
    "anti_slip",
    "adjustable",
    "foldable",
    "rechargeable",
    "shock_absorbing",
    "uv_protection",
    "machine_washable",
    "compact",
    "durable",
    "ergonomic",
    "leak_proof",
    "insulating",
    "high_grip",
    "reflective",
    "seam_sealed",
    "moisture_wicking",
    "anti_bacterial",
    "portable",
    "energy_efficient",
    "warranty_included",
)


# --------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------
class Priority(StrEnum):
    ESSENTIAL = "essential"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


PRIORITY_ORDER: dict[str, int] = {"essential": 0, "recommended": 1, "optional": 2}


class FulfillmentStatus(StrEnum):
    PENDING = "pending"
    FULFILLED = "fulfilled"
    UNFULFILLED = "unfulfilled"
    OWNED = "owned"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    COMPLETE = "complete"
    BUDGET_INFEASIBLE = "budget_infeasible"


class BundlePreset(StrEnum):
    BEST_OVERALL = "best_overall"
    BEST_BUDGET = "best_budget"
    PREMIUM = "premium"


class Badge(StrEnum):
    BEST_OVERALL = "best_overall"
    BEST_BUDGET = "best_budget"
    BEST_RATED = "best_rated"
    BEST_PREMIUM = "best_premium"
    BEST_DEAL = "best_deal"


# --------------------------------------------------------------------------
# User signals
# --------------------------------------------------------------------------
class InteractionType(StrEnum):
    VIEWED = "viewed"
    CLICKED = "clicked"
    LIKED = "liked"
    DISLIKED = "disliked"
    SAVED = "saved"
    NOT_INTERESTED = "not_interested"
    PURCHASED = "purchased"


class FeedbackType(StrEnum):
    RELEVANT = "relevant"
    NOT_RELEVANT = "not_relevant"
    SAVED = "saved"
    NOT_INTERESTED = "not_interested"


class PriceBias(StrEnum):
    VALUE = "value"
    BALANCED = "balanced"
    PREMIUM = "premium"


class DeliveryBias(StrEnum):
    FAST = "fast"
    STANDARD = "standard"


class OfferType(StrEnum):
    DISCOUNT = "discount"
    COUPON = "coupon"
    BANK_OFFER = "bank_offer"
    BUNDLE = "bundle"


# --------------------------------------------------------------------------
# Errors (see docs/API_CONTRACT.md)
# --------------------------------------------------------------------------
class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    REQUIREMENT_NOT_FOUND = "REQUIREMENT_NOT_FOUND"
    BUDGET_INFEASIBLE = "BUDGET_INFEASIBLE"
    NO_PRODUCTS_FOUND = "NO_PRODUCTS_FOUND"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    UNAUTHORIZED = "UNAUTHORIZED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
