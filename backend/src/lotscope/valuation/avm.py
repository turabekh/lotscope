import re
from dataclasses import dataclass
from datetime import date
from statistics import mean, median, pstdev, quantiles
from typing import Literal

Confidence = Literal["high", "medium", "low"]

_HIGH_MIN_COMPS = 5
_HIGH_MAX_CV = 0.25
_MEDIUM_MIN_COMPS = 3
_MEDIUM_MAX_CV = 0.5
_MIN_COMPS_FOR_TRIM = 4
_IQR_FENCE = 1.5

_MIN_NAME_TOKEN_LEN = 3
_NAME_STOPWORDS = frozenset(
    {
        "JR",
        "SR",
        "II",
        "III",
        "IV",
        "LLC",
        "INC",
        "CO",
        "CORP",
        "LP",
        "LLP",
        "LTD",
        "TRUST",
        "TRUSTEE",
        "TRUSTEES",
        "ESTATE",
        "ETAL",
        "THE",
        "AND",
    }
)
_NAME_TOKEN_RE = re.compile(r"[A-Z]+")


def _name_tokens(name: str | None) -> frozenset[str]:
    if not name:
        return frozenset()
    tokens = _NAME_TOKEN_RE.findall(name.upper())
    return frozenset(
        token
        for token in tokens
        if len(token) >= _MIN_NAME_TOKEN_LEN and token not in _NAME_STOPWORDS
    )


def is_related_party(grantor: str | None, grantee: str | None) -> bool:
    return bool(_name_tokens(grantor) & _name_tokens(grantee))


@dataclass(frozen=True)
class Comp:
    parcel_number: str
    distance_ft: float
    sale_price: float
    sale_date: date | None
    lot_area_sqft: float | None
    price_per_sqft: float | None
    address: str | None = None


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


def trim_outlier_rates(rates: list[float]) -> tuple[list[float], int]:
    if len(rates) < _MIN_COMPS_FOR_TRIM:
        return rates, 0
    q1, _, q3 = quantiles(rates, n=4, method="inclusive")
    iqr = q3 - q1
    if iqr <= 0:
        return rates, 0
    lower = q1 - _IQR_FENCE * iqr
    upper = q3 + _IQR_FENCE * iqr
    kept = [rate for rate in rates if lower <= rate <= upper]
    if len(kept) < _MEDIUM_MIN_COMPS:
        return rates, 0
    return kept, len(rates) - len(kept)


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


def estimate_land_value(
    subject_area_sqft: float | None,
    comps: list[Comp],
    *,
    related_party_excluded: int = 0,
) -> ValuationEstimate:
    if subject_area_sqft is None or subject_area_sqft <= 0:
        return _unknown(len(comps), "Subject lot area is unknown; cannot estimate land value.")

    rates = [c.price_per_sqft for c in comps if c.price_per_sqft and c.price_per_sqft > 0]
    if not rates:
        return _unknown(
            len(comps), "No comparable land sales with a usable price per square foot were found."
        )

    usable_rates, trimmed = trim_outlier_rates(rates)
    median_rate = median(usable_rates)
    average_rate = mean(usable_rates)
    cv = pstdev(usable_rates) / average_rate if len(usable_rates) > 1 and average_rate else 0.0
    estimate = round(median_rate * subject_area_sqft)
    low = round(min(usable_rates) * subject_area_sqft)
    high = round(max(usable_rates) * subject_area_sqft)
    confidence = _confidence(len(usable_rates), cv)

    reasons = [
        f"Estimate from {len(usable_rates)} comparable land sale(s); median "
        f"${median_rate:,.0f}/sqft applied to {subject_area_sqft:,.0f} sqft.",
        f"Price dispersion (coefficient of variation) ~{cv:.2f}.",
    ]
    if trimmed:
        reasons.append(
            f"Excluded {trimmed} price-per-sqft outlier(s) beyond the interquartile fence."
        )
    if related_party_excluded:
        reasons.append(
            f"Excluded {related_party_excluded} likely related-party sale(s) "
            "sharing an owner surname."
        )
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
