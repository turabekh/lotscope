from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]

_WEIGHT: dict[Severity, float] = {"high": 40.0, "medium": 20.0, "low": 10.0, "info": 0.0}
_HIGH_RISK_FLOOD_ZONES = frozenset({"A", "AE", "AO", "AH", "VE", "V"})
_TAX_HIGH_DUE = 10000.0
_TAX_HIGH_YEARS = 3


@dataclass(frozen=True)
class TaxSignal:
    is_delinquent: bool | None
    total_due: float | None
    years_owed: int | None
    in_sheriff_sale: bool | None


@dataclass(frozen=True)
class LiSignal:
    violations: int = 0
    has_unsafe: bool = False
    has_imminently_dangerous: bool = False
    demolitions: int = 0


@dataclass(frozen=True)
class RiskSignals:
    li: LiSignal
    tax: TaxSignal | None = None
    is_city_owned: bool | None = None
    flood_zones: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskFlag:
    code: str
    severity: Severity
    label: str
    detail: str
    source: str


@dataclass(frozen=True)
class RiskAssessment:
    risk_score: float
    flags: list[RiskFlag]
    summary: str
    confidence: Confidence


def _tax_flags(tax: TaxSignal) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    if tax.in_sheriff_sale:
        flags.append(
            RiskFlag(
                "sheriff_sale",
                "high",
                "Sheriff-sale exposure",
                "Parcel is flagged for sheriff sale.",
                "tax_status",
            )
        )
    if tax.is_delinquent:
        due = tax.total_due or 0.0
        detail = f"${due:,.0f} owed"
        if tax.years_owed:
            detail += f" over {tax.years_owed} year(s)"
        severity: Severity = (
            "high" if due >= _TAX_HIGH_DUE or (tax.years_owed or 0) >= _TAX_HIGH_YEARS else "medium"
        )
        flags.append(
            RiskFlag("tax_delinquency", severity, "Tax delinquency", detail + ".", "tax_status")
        )
    return flags


def _li_flags(li: LiSignal) -> list[RiskFlag]:
    flags: list[RiskFlag] = []
    if li.has_imminently_dangerous:
        flags.append(
            RiskFlag(
                "imminently_dangerous",
                "high",
                "Imminently dangerous",
                "L&I has an imminently-dangerous designation on this parcel.",
                "li_event",
            )
        )
    elif li.has_unsafe:
        flags.append(
            RiskFlag(
                "unsafe_structure",
                "high",
                "Unsafe structure",
                "L&I has an unsafe designation on this parcel.",
                "li_event",
            )
        )
    if li.violations > 0:
        severity: Severity = "medium" if li.violations >= 3 else "low"
        flags.append(
            RiskFlag(
                "li_violations",
                severity,
                "L&I violations on record",
                f"{li.violations} violation(s) on record.",
                "li_event",
            )
        )
    if li.demolitions > 0:
        flags.append(
            RiskFlag(
                "demolition",
                "info",
                "Demolition on record",
                f"{li.demolitions} demolition record(s).",
                "li_event",
            )
        )
    return flags


def _flood_flag(flood_zones: list[str]) -> RiskFlag | None:
    if not flood_zones:
        return None
    severity: Severity = (
        "high" if any(zone in _HIGH_RISK_FLOOD_ZONES for zone in flood_zones) else "medium"
    )
    return RiskFlag(
        "flood_zone",
        severity,
        "FEMA flood zone",
        f"Intersects flood zone(s): {', '.join(flood_zones)}.",
        "flood_zone",
    )


def _summarize(flags: list[RiskFlag]) -> str:
    if not flags:
        return "No major risk flags found."
    severities = [flag.severity for flag in flags]
    for level in ("high", "medium", "low", "info"):
        if level in severities:
            return f"{len(flags)} risk flag(s); highest severity {level}."
    return f"{len(flags)} risk flag(s)."


def assess_risk(signals: RiskSignals) -> RiskAssessment:
    flags: list[RiskFlag] = []
    if signals.tax is not None:
        flags.extend(_tax_flags(signals.tax))
    flags.extend(_li_flags(signals.li))
    if signals.is_city_owned:
        flags.append(
            RiskFlag(
                "public_ownership",
                "medium",
                "Publicly owned",
                "Parcel appears to be city or Land Bank owned; acquisition is through the "
                "public disposition process, not a private sale.",
                "parcel",
            )
        )
    flood_flag = _flood_flag(signals.flood_zones)
    if flood_flag is not None:
        flags.append(flood_flag)

    risk_score = min(100.0, sum(_WEIGHT[flag.severity] for flag in flags))
    confidence: Confidence = "high" if signals.tax is not None else "medium"
    return RiskAssessment(
        risk_score=risk_score,
        flags=flags,
        summary=_summarize(flags),
        confidence=confidence,
    )
