from dataclasses import dataclass
from datetime import date
from statistics import mean, median, pstdev
from typing import Literal

Confidence = Literal["high", "medium", "low"]

_HIGH_MIN_COMPS = 5
_HIGH_MAX_CV = 0.25
_MEDIUM_MIN_COMPS = 3
_MEDIUM_MAX_CV = 0.5


@dataclass(frozen=True)
class Comp:
    parcel_number: str
    distance_ft: float
    sale_price: float
    sale_date: date | None
    lot_area_sqft: float | None
    price_per_sqft: float | None


@dataclass(frozen=True)
class ValuationEstimate:
    estimate: float | None
    low: float | None
    high: float | None
    price_per_sqft: float | None
    confidence: Confidence
    comp_count: int
    coefficient_of_variation: float | None
    reasons: list[str]


_USE_CLASS_BY_PREFIX = {
    "R": "residential",
    "C": "commercial",
    "I": "industrial",
    "S": "special",
}


def land_use_class(base_zoning_code: str | None) -> str | None:
    if not base_zoning_code:
        return None
    return _USE_CLASS_BY_PREFIX.get(base_zoning_code.strip().upper()[:1])


def price_per_sqft(sale_price: float, lot_area_sqft: float | None) -> float | None:
    if lot_area_sqft is None or lot_area_sqft <= 0:
        return None
    return sale_price / lot_area_sqft


def _confidence(usable_comps: int, cv: float | None) -> Confidence:
    if cv is None:
        return "low"
    if usable_comps >= _HIGH_MIN_COMPS and cv < _HIGH_MAX_CV:
        return "high"
    if usable_comps >= _MEDIUM_MIN_COMPS and cv < _MEDIUM_MAX_CV:
        return "medium"
    return "low"


def _unknown(comp_count: int, reason: str) -> ValuationEstimate:
    return ValuationEstimate(
        estimate=None,
        low=None,
        high=None,
        price_per_sqft=None,
        confidence="low",
        comp_count=comp_count,
        coefficient_of_variation=None,
        reasons=[reason],
    )


def estimate_land_value(subject_area_sqft: float | None, comps: list[Comp]) -> ValuationEstimate:
    if subject_area_sqft is None or subject_area_sqft <= 0:
        return _unknown(len(comps), "Subject lot area is unknown; cannot estimate land value.")

    rates = [c.price_per_sqft for c in comps if c.price_per_sqft and c.price_per_sqft > 0]
    if not rates:
        return _unknown(
            len(comps), "No comparable land sales with a usable price per square foot were found."
        )

    median_rate = median(rates)
    average_rate = mean(rates)
    cv = pstdev(rates) / average_rate if len(rates) > 1 and average_rate else 0.0
    estimate = round(median_rate * subject_area_sqft)
    low = round(min(rates) * subject_area_sqft)
    high = round(max(rates) * subject_area_sqft)
    confidence = _confidence(len(rates), cv)

    reasons = [
        f"Estimate from {len(rates)} comparable land sale(s); median "
        f"${median_rate:,.0f}/sqft applied to {subject_area_sqft:,.0f} sqft.",
        f"Price dispersion (coefficient of variation) ~{cv:.2f}.",
    ]
    return ValuationEstimate(
        estimate=float(estimate),
        low=float(low),
        high=float(high),
        price_per_sqft=round(median_rate, 2),
        confidence=confidence,
        comp_count=len(comps),
        coefficient_of_variation=round(cv, 3),
        reasons=reasons,
    )
