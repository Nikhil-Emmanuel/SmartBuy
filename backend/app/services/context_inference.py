"""Infer context the user did not state, instead of asking for it.

Master prompt section 11: ask only questions that materially affect the
recommendation. Season, region type and expected temperature are all
derivable from a place name and the calendar, so we derive them -- and then
show them in the sidebar as correctable assumptions rather than pretending
we were told.

Owner: Member 4 (Requirements) with Member 5 (Agent).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# region_type, approximate winter overnight low, approximate summer low.
# Coarse on purpose: it only needs to be right enough to pick a jacket weight.
LOCATIONS: dict[str, tuple[str, int, int]] = {
    "manali": ("mountain", -5, 12),
    "leh": ("mountain", -14, 8),
    "ladakh": ("mountain", -14, 8),
    "spiti": ("mountain", -15, 6),
    "kasol": ("mountain", -2, 14),
    "shimla": ("mountain", -1, 15),
    "mussoorie": ("mountain", 1, 16),
    "nainital": ("mountain", 1, 15),
    "dharamshala": ("mountain", 2, 17),
    "mcleodganj": ("mountain", 1, 16),
    "darjeeling": ("mountain", 2, 13),
    "gangtok": ("mountain", 4, 15),
    "sikkim": ("mountain", 0, 13),
    "kedarnath": ("mountain", -8, 8),
    "badrinath": ("mountain", -9, 8),
    "rishikesh": ("mountain", 8, 22),
    "uttarakhand": ("mountain", 0, 14),
    "himachal": ("mountain", -3, 13),
    "kashmir": ("mountain", -6, 12),
    "gulmarg": ("mountain", -8, 9),
    "sandakphu": ("mountain", -6, 10),
    "hampta": ("mountain", -8, 8),
    "chadar": ("mountain", -25, 5),
    "everest": ("mountain", -20, 2),
    "annapurna": ("mountain", -12, 6),
    "munnar": ("mountain", 12, 18),
    "ooty": ("mountain", 8, 16),
    "coorg": ("forest", 14, 19),
    "wayanad": ("forest", 15, 20),
    "chikmagalur": ("forest", 13, 18),
    "goa": ("coastal", 20, 26),
    "mumbai": ("coastal", 18, 26),
    "chennai": ("coastal", 20, 27),
    "kochi": ("coastal", 22, 26),
    "pondicherry": ("coastal", 21, 26),
    "andaman": ("coastal", 23, 26),
    "jaisalmer": ("desert", 8, 28),
    "jodhpur": ("desert", 10, 27),
    "rajasthan": ("desert", 8, 27),
    "delhi": ("urban", 6, 26),
    "bangalore": ("urban", 15, 21),
    "bengaluru": ("urban", 15, 21),
    "hyderabad": ("urban", 15, 25),
    "pune": ("urban", 11, 23),
    "kolkata": ("urban", 13, 26),
    "ahmedabad": ("urban", 12, 27),
    "jaipur": ("urban", 8, 27),
    "lucknow": ("urban", 8, 26),
    "chandigarh": ("urban", 6, 25),
}

# Northern-hemisphere Indian calendar.
MONTH_SEASON: dict[int, str] = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "summer", 5: "summer", 6: "summer",
    7: "monsoon", 8: "monsoon", 9: "monsoon",
    10: "autumn", 11: "autumn",
}


@dataclass
class Assumption:
    slot: str
    value: object
    basis: str

    def to_dict(self) -> dict:
        return {"slot": self.slot, "value": self.value, "basis": self.basis}


def lookup_location(location: str | None) -> tuple[str, int, int] | None:
    if not location:
        return None
    lowered = location.lower().strip()
    if lowered in LOCATIONS:
        return LOCATIONS[lowered]
    # Substring match handles "Manali, Himachal Pradesh" and "near Leh".
    for name, data in LOCATIONS.items():
        if name in lowered:
            return data
    return None


def infer_season(location: str | None, when: date | None = None) -> tuple[str, str]:
    """Return (season, basis). Never asked -- always derived."""
    month = (when or date.today()).month
    season = MONTH_SEASON[month]
    month_name = (when or date.today()).strftime("%B")
    if location:
        return season, f"{location.title()} in {month_name}"
    return season, f"travel in {month_name}"


def infer_context(context: dict, today: date | None = None) -> tuple[dict, list[Assumption]]:
    """Fill derivable slots and report what we assumed.

    Never overwrites something the user actually told us.
    """
    ctx = dict(context)
    assumptions: list[Assumption] = []

    start = ctx.get("start_date")
    when = today or date.today()
    if isinstance(start, str) and start:
        try:
            when = date.fromisoformat(start[:10])
        except ValueError:
            pass
    elif isinstance(start, date):
        when = start

    location = ctx.get("location")
    entry = lookup_location(location)

    # --- season ---
    if not ctx.get("season"):
        season, basis = infer_season(location, when)
        ctx["season"] = season
        assumptions.append(Assumption("season", season, basis))
    season = ctx["season"]

    # --- region type ---
    if not ctx.get("region_type"):
        if entry:
            ctx["region_type"] = entry[0]
            assumptions.append(
                Assumption("region_type", entry[0], f"{str(location).title()} is a {entry[0]} region")
            )
        elif ctx.get("activity") in ("trek", "winter_trek", "hiking"):
            ctx["region_type"] = "mountain"
            assumptions.append(Assumption("region_type", "mountain", "trekking usually means hills"))

    # --- expected overnight low ---
    if ctx.get("temp_min_c") is None:
        if entry:
            _, winter_low, summer_low = entry
            temp = winter_low if season == "winter" else (
                summer_low if season == "summer" else round((winter_low + summer_low) / 2)
            )
            basis = f"typical {season} overnight low in {str(location).title()}"
        else:
            defaults = {"winter": 5, "spring": 14, "summer": 22, "monsoon": 19, "autumn": 12}
            temp = defaults.get(season, 15)
            basis = f"typical {season} overnight low"
            if ctx.get("region_type") == "mountain":
                temp -= 8
                basis = f"typical {season} overnight low in the hills"
        ctx["temp_min_c"] = temp
        assumptions.append(Assumption("temp_min_c", temp, basis))

    # --- cheap structural defaults ---
    if not ctx.get("people_count"):
        ctx["people_count"] = 1
    if ctx.get("duration_days") is None and ctx.get("activity") in ("laptop_purchase", "apartment_setup"):
        ctx["duration_days"] = 1

    return ctx, assumptions
