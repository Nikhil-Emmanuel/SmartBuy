"""Serving the shopper-segment model.

Loads the artifact trained by `ml/personalization/train.py` once per process,
scores a user's behaviour, and turns the prediction into an offer via the
policy in `app/ml/segments.py`.

Three things this deliberately will not do:

* It will not predict for a user with too little history. Under `min_events`
  the vector is mostly zeros and the model would still return a confident
  class, which is worse than returning nothing.
* It will not act on a low-confidence prediction (`MIN_CONFIDENCE`). Guessing
  someone's segment and discounting on the guess is how personalisation ends up
  feeling creepy and arbitrary.
* It will not fail a request. No model file, stale features, unreadable
  artifact -- all of it degrades to "no personalised offer", the same as a
  brand-new user.

The model never writes to the database. It proposes an offer; persisting one
is a separate, validated step.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.ml.features import FEATURE_NAMES, build_features
from app.ml.segments import MIN_CONFIDENCE, offer_for

log = logging.getLogger("smartbuy.personalization")

MODEL_PATH = (
    Path(__file__).resolve().parents[3]
    / "ml" / "personalization" / "model" / "segment_classifier.joblib"
)

_lock = threading.Lock()
_bundle: dict | None = None
_load_attempted = False


@dataclass(frozen=True)
class Personalization:
    """What we are prepared to say about a user, and how sure we are."""

    segment: str | None
    label: str | None
    confidence: float
    rationale: str | None
    discount_pct: int
    coupon_code: str | None
    perk: str | None
    events_considered: int
    status: str  # ok | insufficient_history | low_confidence | model_unavailable

    def to_dict(self) -> dict:
        return asdict(self)


def _empty(status: str, events: int = 0) -> Personalization:
    return Personalization(
        segment=None, label=None, confidence=0.0, rationale=None,
        discount_pct=0, coupon_code=None, perk=None,
        events_considered=events, status=status,
    )


def _load() -> dict | None:
    """Load the artifact once. A missing model is normal, not an error.

    The repo ships without one until `ml/personalization/train.py` has been
    run, and a fresh clone must still boot.
    """
    global _bundle, _load_attempted
    if _bundle is not None or _load_attempted:
        return _bundle
    with _lock:
        if _bundle is not None or _load_attempted:
            return _bundle
        _load_attempted = True
        if not MODEL_PATH.exists():
            log.info("No segment model at %s -- personalisation disabled.", MODEL_PATH)
            return None
        try:
            import joblib

            bundle = joblib.load(MODEL_PATH)
        except Exception:
            log.exception("Could not load the segment model; personalisation disabled.")
            return None

        trained_on = tuple(bundle.get("feature_names", ()))
        if trained_on != FEATURE_NAMES:
            # Refusing here is the whole point of storing the names. A model
            # fed columns in a different order does not error -- it returns
            # confident nonsense.
            log.error(
                "Segment model was trained on different features (%d vs %d); "
                "refusing to use it. Retrain with ml/personalization/train.py.",
                len(trained_on), len(FEATURE_NAMES),
            )
            return None
        _bundle = bundle
        log.info("Segment model loaded: classes=%s", bundle.get("classes"))
        return _bundle


def personalize(db: Session, user_id: str) -> Personalization:
    """Predict the user's segment and the offer that follows from it."""
    bundle = _load()
    if bundle is None:
        return _empty("model_unavailable")

    rows = build_features(db, [user_id])
    if not rows:
        return _empty("insufficient_history")

    row = rows[0]
    if row.n_events < int(bundle.get("min_events", 10)):
        return _empty("insufficient_history", row.n_events)

    model = bundle["model"]
    probabilities = model.predict_proba([row.values])[0]
    best = int(probabilities.argmax())
    segment = str(model.classes_[best])
    confidence = float(probabilities[best])

    if confidence < MIN_CONFIDENCE:
        return _empty("low_confidence", row.n_events)

    offer = offer_for(segment)
    if offer is None:
        log.warning("Model predicted %r with no offer policy defined.", segment)
        return _empty("low_confidence", row.n_events)

    return Personalization(
        segment=segment,
        label=offer.label,
        confidence=round(confidence, 3),
        rationale=offer.rationale,
        discount_pct=offer.discount_pct,
        coupon_code=offer.coupon_code,
        perk=offer.perk,
        events_considered=row.n_events,
        status="ok",
    )


def model_info() -> dict:
    """What is loaded, for the admin page and for /api/health."""
    bundle = _load()
    if bundle is None:
        return {"loaded": False, "path": str(MODEL_PATH), "classes": []}
    return {
        "loaded": True,
        "path": str(MODEL_PATH),
        "classes": [str(c) for c in bundle.get("classes", [])],
        "n_features": len(bundle.get("feature_names", ())),
        "min_events": bundle.get("min_events"),
    }
