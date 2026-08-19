"""Shopper segments and the offer each one is sent.

Deliberately split from the model. The classifier's job is to answer "which
segment does this behaviour look like"; deciding what to *do* about that answer
is a commercial policy, and policy that lives inside a model is policy nobody
can review. Changing a discount here does not require retraining anything.

The policy itself follows one rule: discount where a discount changes the
outcome, and not where it only costs margin.
"""

from __future__ import annotations

from dataclasses import dataclass

# Below this the classifier is not confident enough to act on. The user still
# gets the catalog-wide offers -- they simply do not get a personalised one,
# which is the correct behaviour when we do not know who we are talking to.
MIN_CONFIDENCE = 0.55


@dataclass(frozen=True)
class SegmentOffer:
    segment: str
    label: str
    rationale: str          # why this behaviour implies this offer, in plain words
    discount_pct: int
    coupon_code: str | None
    perk: str | None        # what they get instead when a discount is wrong


SEGMENT_OFFERS: dict[str, SegmentOffer] = {
    "deal_seeker": SegmentOffer(
        segment="deal_seeker",
        label="Deal seeker",
        rationale=(
            "Browses and buys heavily discounted items, and converts markedly "
            "more often when the discount is deep. A coupon moves this basket."
        ),
        discount_pct=10,
        coupon_code="SMARTBUY10",
        perk=None,
    ),
    "window_shopper": SegmentOffer(
        segment="window_shopper",
        label="Still deciding",
        rationale=(
            "High browsing volume with very few purchases. The barrier is "
            "commitment rather than selection, so this is where a first-order "
            "incentive is worth the most."
        ),
        discount_pct=15,
        coupon_code="FIRSTBUY15",
        perk=None,
    ),
    "brand_loyal": SegmentOffer(
        segment="brand_loyal",
        label="Brand loyal",
        rationale=(
            "Activity concentrates on a small number of brands. A blanket "
            "discount is wasted here; relevance to those brands is not."
        ),
        discount_pct=5,
        coupon_code="LOYAL5",
        perk="Early access to new arrivals from the brands you follow",
    ),
    "premium_buyer": SegmentOffer(
        segment="premium_buyer",
        label="Quality first",
        rationale=(
            "Buys high-rated, higher-priced items and converts without needing "
            "a discount. Discounting this segment would cost margin and change "
            "nothing, so the offer is service rather than price."
        ),
        discount_pct=0,
        coupon_code=None,
        perk="Free express delivery and extended returns",
    ),
}

SEGMENT_NAMES: tuple[str, ...] = tuple(sorted(SEGMENT_OFFERS))


def offer_for(segment: str) -> SegmentOffer | None:
    return SEGMENT_OFFERS.get(segment)
