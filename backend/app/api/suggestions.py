"""Pre-filled things the user can actually ask for.

The chat used to be a blank box, which invites questions the catalog cannot
answer -- "mobile" being the obvious one, since we stock no phones. Every
option returned here is derived from data that exists: goals come from the YAML
knowledge base, categories come from a live count over the products table.

If a suggestion is on screen, the system can answer it. That is the whole
contract of this endpoint, and it is why nothing here is hard-coded.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.kb.loader import list_goals
from app.models.product import Product

router = APIRouter(prefix="/api", tags=["suggestions"])

# How many category chips to offer. Enough to feel like a real catalog, few
# enough to scan in one glance.
TOP_CATEGORIES = 8
MIN_PRODUCTS = 20


class Suggestion(BaseModel):
    label: str = Field(..., description="What the chip says.")
    message: str = Field(..., description="What gets sent to /api/chat when clicked.")
    kind: str = Field(..., description="goal | category")
    detail: str | None = Field(None, description="Supporting line, e.g. a product count.")


class SuggestionsResponse(BaseModel):
    goals: list[Suggestion]
    categories: list[Suggestion]
    source: str = Field(
        "catalog",
        description=(
            "Always 'catalog': these are generated from the knowledge base and a "
            "live product count, never from a static list."
        ),
    )


# The example sentence per goal. Phrased as a real opening message so that the
# agent's slot extraction has something to chew on -- a bare goal name would
# just trigger the follow-up questions immediately.
#
# Two of them mention things the user already owns. That is deliberate: these
# sentences are also what the landing page rotates through, and the exclusion
# rule is one of the few behaviours a single sentence can demonstrate.
GOAL_OPENERS: dict[str, str] = {
    "winter_trek": (
        "I'm going on a 4-day winter trek in Manali, budget ₹15,000, I'm a beginner "
        "and I already have trekking shoes and a backpack"
    ),
    "trek": "I'm planning a 3-day trek next month, budget ₹12,000",
    "camping": "I'm going camping overnight with 2 people, budget ₹10,000",
    "laptop_purchase": "I need a laptop for college work, budget ₹60,000",
    "apartment_setup": (
        "I'm moving into my first 1BHK apartment on a ₹40,000 budget "
        "and I have nothing except a mattress"
    ),
}


@router.get("/suggestions", response_model=SuggestionsResponse)
def get_suggestions(db: DbSession) -> SuggestionsResponse:
    """Options the user can click instead of guessing what we stock."""
    goals = [
        Suggestion(
            label=goal.display_name,
            # Fall back to the goal name rather than skipping a goal we forgot
            # to write an opener for -- a missing chip is worse than a plain one.
            message=GOAL_OPENERS.get(goal.key, f"I'm planning {goal.display_name.lower()}"),
            kind="goal",
            detail=f"{len(goal.items)} items planned for you",
        )
        for goal in list_goals()
    ]

    rows = db.execute(
        select(Product.category, func.count(Product.id).label("n"))
        .group_by(Product.category)
        .having(func.count(Product.id) >= MIN_PRODUCTS)
        .order_by(func.count(Product.id).desc())
        .limit(TOP_CATEGORIES)
    ).all()

    categories = [
        Suggestion(
            label=category.replace("_", " ").title(),
            message=f"Show me {category.replace('_', ' ')}",
            kind="category",
            detail=f"{n} products",
        )
        for category, n in rows
    ]

    return SuggestionsResponse(goals=goals, categories=categories)
