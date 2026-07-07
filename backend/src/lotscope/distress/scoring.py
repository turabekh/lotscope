from dataclasses import dataclass
from typing import Literal

from lotscope.distress.profiles import DistressScoringProfile

Tier = Literal["high", "medium", "low", "none"]

DISTRESS_VERSION = "v2"


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


def _tier(score: int, profile: DistressScoringProfile) -> Tier:
    if score >= profile.high_tier:
        return "high"
    if score >= profile.medium_tier:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def is_absentee(address: str | None, mailing_address: str | None) -> bool:
    if not address or not mailing_address:
        return False
    return address.strip().upper() not in mailing_address.strip().upper()


def score_distress(
    signals: DistressSignals, profile: DistressScoringProfile
) -> DistressAssessment:
    if signals.is_city_owned:
        return DistressAssessment(score=0, tier="none", factors=[])

    factors: list[DistressFactor] = []

    if signals.in_sheriff_sale:
        factors.append(
            DistressFactor("sheriff_sale", "Sheriff-sale exposure", profile.sheriff_sale_weight)
        )
    if signals.is_delinquent:
        due = signals.total_due or 0.0
        factors.append(
            DistressFactor(
                "tax_delinquent", f"Tax delinquent (${due:,.0f})", profile.delinquent_weight
            )
        )
        if due >= profile.severe_due or (signals.years_owed or 0) >= profile.severe_years:
            factors.append(
                DistressFactor(
                    "severe_delinquency",
                    "Severe or long-running tax delinquency",
                    profile.severe_delinquent_weight,
                )
            )
    if (signals.lien_count or 0) > 0:
        factors.append(
            DistressFactor("liens", f"{signals.lien_count} tax lien(s)", profile.lien_weight)
        )
    if signals.has_imminently_dangerous or signals.has_unsafe:
        factors.append(
            DistressFactor(
                "li_dangerous", "Unsafe or dangerous structure (L&I)", profile.dangerous_weight
            )
        )
    elif signals.violations > 0:
        factors.append(
            DistressFactor("li_violations", "Open L&I violations", profile.violation_weight)
        )
    if signals.demolitions > 0:
        factors.append(
            DistressFactor("demolition", "Demolition on record", profile.demolition_weight)
        )
    if signals.is_vacant:
        factors.append(
            DistressFactor("vacant", "Vacant lot — owner unlikely to occupy", profile.vacant_weight)
        )
    if signals.is_absentee_owner:
        factors.append(
            DistressFactor(
                "absentee", "Absentee owner (out-of-area mailing address)", profile.absentee_weight
            )
        )
    if (
        signals.is_absentee_owner
        and signals.years_since_last_sale is not None
        and signals.years_since_last_sale >= profile.long_tenure_years
    ):
        held_years = int(signals.years_since_last_sale)
        factors.append(
            DistressFactor(
                "long_tenure",
                f"Long-tenured absentee owner (~{held_years} yrs)",
                profile.long_tenure_weight,
            )
        )
    if signals.is_tired_landlord:
        factors.append(
            DistressFactor(
                "portfolio_distress",
                "Tired landlord (portfolio-wide violations)",
                profile.portfolio_distress_weight,
            )
        )

    score = min(profile.score_cap, sum(factor.weight for factor in factors))
    return DistressAssessment(score=score, tier=_tier(score, profile), factors=factors)
