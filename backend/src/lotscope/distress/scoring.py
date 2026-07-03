from dataclasses import dataclass
from typing import Literal

Tier = Literal["high", "medium", "low", "none"]

DISTRESS_VERSION = "v2"

_SHERIFF_SALE_WEIGHT = 30
_DELINQUENT_WEIGHT = 15
_SEVERE_DELINQUENT_WEIGHT = 15
_LIEN_WEIGHT = 10
_DANGEROUS_WEIGHT = 15
_VIOLATION_WEIGHT = 5
_DEMOLITION_WEIGHT = 5
_VACANT_WEIGHT = 10
_ABSENTEE_WEIGHT = 10
_LONG_TENURE_WEIGHT = 5
_PORTFOLIO_DISTRESS_WEIGHT = 10

_SEVERE_DUE = 10000.0
_SEVERE_YEARS = 3
_LONG_TENURE_YEARS = 15.0
_HIGH_TIER = 60
_MEDIUM_TIER = 30


@dataclass(frozen=True)
class DistressSignals:
    in_sheriff_sale: bool = False
    is_delinquent: bool = False
    total_due: float | None = None
    years_owed: int | None = None
    lien_count: int | None = None
    has_unsafe: bool = False
    has_imminently_dangerous: bool = False
    violations: int = 0
    demolitions: int = 0
    is_vacant: bool = False
    is_absentee_owner: bool = False
    is_city_owned: bool = False
    years_since_last_sale: float | None = None
    is_tired_landlord: bool = False


@dataclass(frozen=True)
class DistressFactor:
    code: str
    label: str
    weight: int


@dataclass(frozen=True)
class DistressAssessment:
    score: int
    tier: Tier
    factors: list[DistressFactor]


def _tier(score: int) -> Tier:
    if score >= _HIGH_TIER:
        return "high"
    if score >= _MEDIUM_TIER:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def is_absentee(address: str | None, mailing_address: str | None) -> bool:
    if not address or not mailing_address:
        return False
    return address.strip().upper() not in mailing_address.strip().upper()


def score_distress(signals: DistressSignals) -> DistressAssessment:
    if signals.is_city_owned:
        return DistressAssessment(score=0, tier="none", factors=[])

    factors: list[DistressFactor] = []

    if signals.in_sheriff_sale:
        factors.append(
            DistressFactor("sheriff_sale", "Sheriff-sale exposure", _SHERIFF_SALE_WEIGHT)
        )
    if signals.is_delinquent:
        due = signals.total_due or 0.0
        factors.append(
            DistressFactor("tax_delinquent", f"Tax delinquent (${due:,.0f})", _DELINQUENT_WEIGHT)
        )
        if due >= _SEVERE_DUE or (signals.years_owed or 0) >= _SEVERE_YEARS:
            factors.append(
                DistressFactor(
                    "severe_delinquency",
                    "Severe or long-running tax delinquency",
                    _SEVERE_DELINQUENT_WEIGHT,
                )
            )
    if (signals.lien_count or 0) > 0:
        factors.append(DistressFactor("liens", f"{signals.lien_count} tax lien(s)", _LIEN_WEIGHT))
    if signals.has_imminently_dangerous or signals.has_unsafe:
        factors.append(
            DistressFactor("li_dangerous", "Unsafe or dangerous structure (L&I)", _DANGEROUS_WEIGHT)
        )
    elif signals.violations > 0:
        factors.append(DistressFactor("li_violations", "Open L&I violations", _VIOLATION_WEIGHT))
    if signals.demolitions > 0:
        factors.append(DistressFactor("demolition", "Demolition on record", _DEMOLITION_WEIGHT))
    if signals.is_vacant:
        factors.append(
            DistressFactor("vacant", "Vacant lot — owner unlikely to occupy", _VACANT_WEIGHT)
        )
    if signals.is_absentee_owner:
        factors.append(
            DistressFactor(
                "absentee", "Absentee owner (out-of-area mailing address)", _ABSENTEE_WEIGHT
            )
        )
    if (
        signals.is_absentee_owner
        and signals.years_since_last_sale is not None
        and signals.years_since_last_sale >= _LONG_TENURE_YEARS
    ):
        held_years = int(signals.years_since_last_sale)
        factors.append(
            DistressFactor(
                "long_tenure",
                f"Long-tenured absentee owner (~{held_years} yrs)",
                _LONG_TENURE_WEIGHT,
            )
        )
    if signals.is_tired_landlord:
        factors.append(
            DistressFactor(
                "portfolio_distress",
                "Tired landlord (portfolio-wide violations)",
                _PORTFOLIO_DISTRESS_WEIGHT,
            )
        )

    score = min(100, sum(factor.weight for factor in factors))
    return DistressAssessment(score=score, tier=_tier(score), factors=factors)
