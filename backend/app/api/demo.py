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
from app.ml.segments import SEGMENT_NAMES
from app.models.product import ProductInteraction
from app.models.user import User, UserPreference

router = APIRouter(prefix="/api/demo", tags=["demo"])

MIN_EVENTS = 10
#: Seats reserved per segment. The roster is stratified rather than ranked --
#: see `_roster` for why ranking by activity silently collapsed it to one class.
PER_SEGMENT = 2
MAX_SHOPPERS = PER_SEGMENT * len(SEGMENT_NAMES)


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


def _roster(rows: list) -> list:
    """Pick a spread of shoppers: `PER_SEGMENT` from each segment, interleaved.

    This used to be `ORDER BY interaction_count DESC LIMIT 8`, which is not the
    neutral tie-break it looks like. Window shoppers browse about twice as much
    as every other segment by construction -- that is what makes them window
    shoppers -- so "the eight busiest shoppers" resolved to eight window
    shoppers, every demo account was predicted the same class, and the picker
    handed out the same 15% coupon eight times over.

    Sampling per segment instead is the fix: the roster now spans all four
    archetypes, so switching shoppers visibly changes the prediction, the
    metrics and the offer. Activity still orders the candidates *within* a
    segment, since a longer history yields a more confident prediction.

    Lead interests are kept distinct across the whole roster where the data
    allows, so no two cards read "Kitchen browser".
    """
    by_segment: dict[str, list] = {}
    for row in rows:
        by_segment.setdefault(row.segment, []).append(row)

    picked: dict[str, list] = {}
    seen_leads: set[str | None] = set()

    for segment in SEGMENT_NAMES:
        candidates = by_segment.get(segment, [])
        chosen: list = []

        # First pass takes only shoppers whose lead interest is still unused.
        for row in candidates:
            if len(chosen) == PER_SEGMENT:
                break
            lead = (list(row.preferred_categories or []) or [None])[0]
            if lead in seen_leads:
                continue
            chosen.append(row)
            seen_leads.add(lead)

        # Second pass fills any remaining seat, duplicate lead or not. A seat
        # left empty would quietly drop a whole archetype from the demo, which
        # is the exact failure this function exists to prevent.
        if len(chosen) < PER_SEGMENT:
            taken = {r.id for r in chosen}
            for row in candidates:
                if len(chosen) == PER_SEGMENT:
                    break
                if row.id not in taken:
                    chosen.append(row)

        if chosen:
            picked[segment] = chosen

    # Interleave, so the first cards in the list are already four different
    # archetypes rather than two of one followed by two of the next.
    roster: list = []
    for slot in range(PER_SEGMENT):
        for segment in SEGMENT_NAMES:
            if slot < len(picked.get(segment, [])):
                roster.append(picked[segment][slot])
    return roster


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
        select(
            User.id,
            User.created_at,
            UserPreference.preferred_categories,
            UserPreference.segment,
            counts.c.n.label("events"),
        )
        .join(UserPreference, UserPreference.user_id == User.id)
        .join(counts, counts.c.uid == User.id)
        # Only seeded users carry a stored segment; see the module docstring.
        .where(UserPreference.segment != "")
        # `id` breaks ties so the roster is stable between calls -- a picker
        # that reshuffles on every open is not something to demo on stage.
        .order_by(counts.c.n.desc(), User.id)
    ).all()

    shoppers = [
        DemoShopper(
            user_id=str(row.id),
            label=_label(list(row.preferred_categories or []), i),
            events=int(row.events),
            interests=[c.replace("_", " ") for c in (row.preferred_categories or [])][:3],
            joined=row.created_at.isoformat() if row.created_at else None,
        )
        for i, row in enumerate(_roster(rows), start=1)
    ]
    return DemoShoppersResponse(shoppers=shoppers)
