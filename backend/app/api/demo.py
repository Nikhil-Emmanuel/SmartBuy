"""Demo shopper roster for the sign-in popup.

There is no real authentication in this project (ADR-005) and this does not add
any: "signing in" means adopting the session id of a seeded synthetic shopper
so that the personalised experience can be shown with a real history behind it.

Why this is not a privacy hole: every row it returns is fabricated by
`backend/scripts/seed.py`. The filter is `UserPreference.segment != ""`, and
only the seeder ever writes that column -- a real user's segment is predicted,
never stored. So this endpoint cannot return a real person's account, and it
is the reason the filter is written that way rather than "all users".

It is still a demo affordance, not a product feature. Nothing in the normal
user journey calls it.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models.product import ProductInteraction
from app.models.user import User, UserPreference

router = APIRouter(prefix="/api/demo", tags=["demo"])

MAX_SHOPPERS = 8
MIN_EVENTS = 10


class DemoShopper(BaseModel):
    user_id: str
    label: str = Field(..., description="Display name generated from their interests.")
    events: int = Field(..., description="Recorded interactions behind this shopper.")
    interests: list[str] = Field(default_factory=list)
    joined: str | None = None


class DemoShoppersResponse(BaseModel):
    shoppers: list[DemoShopper]
    is_synthetic: bool = Field(
        True,
        description=(
            "Always true. These are generated shoppers, not real accounts, and "
            "the UI must say so wherever it lists them."
        ),
    )


def _label(interests: list[str], index: int) -> str:
    """A readable name. Their segment is deliberately NOT in it.

    Naming a shopper "Deal seeker" in the picker would hand over the answer the
    model is supposed to produce, and would turn the demo into a tautology.
    """
    if interests:
        lead = interests[0].replace("_", " ").title()
        return f"Shopper {index} · {lead} browser"
    return f"Shopper {index}"


@router.get("/shoppers", response_model=DemoShoppersResponse)
def list_demo_shoppers(db: DbSession) -> DemoShoppersResponse:
    """Seeded synthetic shoppers that have enough history to be classifiable."""
    counts = (
        select(
            ProductInteraction.user_id.label("uid"),
            func.count(ProductInteraction.id).label("n"),
        )
        .group_by(ProductInteraction.user_id)
        .having(func.count(ProductInteraction.id) >= MIN_EVENTS)
        .subquery()
    )

    rows = db.execute(
        select(User.id, User.created_at, UserPreference.preferred_categories, counts.c.n)
        .join(UserPreference, UserPreference.user_id == User.id)
        .join(counts, counts.c.uid == User.id)
        # Only seeded users carry a stored segment; see the module docstring.
        .where(UserPreference.segment != "")
        .order_by(counts.c.n.desc())
        .limit(MAX_SHOPPERS)
    ).all()

    shoppers = [
        DemoShopper(
            user_id=str(user_id),
            label=_label(list(interests or []), i),
            events=int(n),
            interests=[c.replace("_", " ") for c in (interests or [])][:3],
            joined=created_at.isoformat() if created_at else None,
        )
        for i, (user_id, created_at, interests, n) in enumerate(rows, start=1)
    ]
    return DemoShoppersResponse(shoppers=shoppers)
