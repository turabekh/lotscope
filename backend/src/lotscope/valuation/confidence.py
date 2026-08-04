from typing import Literal

ValueConfidence = Literal["high", "medium", "low"]

CONFIDENCE_SCORE: dict[ValueConfidence, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}

_BANDS: tuple[tuple[float, ValueConfidence], ...] = (
    (0.9, "high"),
    (0.6, "medium"),
    (0.0, "low"),
)

_SUPPORT_NOTES: dict[ValueConfidence, str] = {
    "high": "Estimated from recent recorded comparable sales nearby.",
    "medium": (
        "Estimated from recorded comparable sales nearby, but the supporting set is "
        "moderate — treat the range as indicative."
    ),
    "low": (
        "The supporting sales are few, widely spread, or drawn from a wider search "
        "because none were found close by. Treat this as a rough guide, not a market "
        "read for this block."
    ),
}

NO_ESTIMATE_NOTE = "Not enough recorded comparable sales nearby yet."


def value_confidence_band(score: float | None) -> ValueConfidence | None:
    if score is None:
        return None
    for threshold, band in _BANDS:
        if score >= threshold:
            return band
    return "low"


def value_support_note(band: ValueConfidence | None) -> str:
    return NO_ESTIMATE_NOTE if band is None else _SUPPORT_NOTES[band]
