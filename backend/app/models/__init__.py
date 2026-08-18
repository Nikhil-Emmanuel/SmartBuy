"""ORM models. Importing this package registers every table on Base.metadata."""

from app.models.audit import AuditLog
from app.models.feedback import Feedback
from app.models.plan import Requirement, ShoppingPlan
from app.models.product import Offer, Product, ProductInteraction
from app.models.recommendation import (
    BundleItem,
    PlanBundle,
    Recommendation,
    Substitution,
)
from app.models.session import ChatSession, ConversationMessage
from app.models.user import User, UserPreference

__all__ = [
    "AuditLog",
    "BundleItem",
    "ChatSession",
    "ConversationMessage",
    "Feedback",
    "Offer",
    "PlanBundle",
    "Product",
    "ProductInteraction",
    "Recommendation",
    "Requirement",
    "ShoppingPlan",
    "Substitution",
    "User",
    "UserPreference",
]
