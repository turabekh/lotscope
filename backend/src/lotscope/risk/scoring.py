import re
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]

_WEIGHT: dict[Severity, float] = {"high": 40.0, "medium": 20.0, "low": 10.0, "info": 0.0}
_HIGH_RISK_FLOOD_ZONES = frozenset({"A", "AE", "AO", "AH", "VE", "V"})
_TAX_HIGH_DUE = 10000.0
_TAX_HIGH_YEARS = 3
STREET_ACCESS_MAX_FT = 75.0
_ESTATE_RE = re.compile(r"\b(ESTATE OF|HEIRS?|DECEASED|DECD)\b")
_TRAILING_ESTATE_RE = re.compile(r"\bESTATE\b")
_REAL_ESTATE_RE = re.compile(r"\bREAL ESTATE\b")
_BUSINESS_ENTITY_RE = re.compile(
    r"\b(LLC|L L C|INC|LP|LLP|CORP|COMPANY|PARTNERS?|PARTNERSHIP|ASSOC|ASSOCIATES|HOLDINGS|"
    r"GROUP|PROPERTIES|PROPS|INVESTMENTS?|INVESTORS?|REALTY|MGMT|MANAGEMENT|TRUST)\b"
)
_MULTIPLE_OWNERS_RE = re.compile(r"\bET (AL|UX)\b")


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
    open_violations: int = 0
    violation_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class TitleSignal:
    owner: str | None


@dataclass(frozen=True)
class AccessSignal:
    has_geometry: bool
    has_street_frontage: bool


@dataclass(frozen=True)
class RiskSignals:
    li: LiSignal
    tax: TaxSignal | None = None
    is_city_owned: bool | None = None
    flood_zones: list[str] = field(default_factory=list)
    title: TitleSignal | None = None
    access: AccessSignal | None = None


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


def _format_violation_type(value: str) -> str:
    return value.strip().title()


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
        detail = f"{li.violations} violation(s) on record"
        if li.open_violations:
            detail += f", {li.open_violations} still open"
        if li.violation_types:
            kinds = ", ".join(_format_violation_type(value) for value in li.violation_types)
            detail += f" — {kinds}"
        flags.append(
            RiskFlag(
                "li_violations",
                severity,
                "L&I violations on record",
                detail + ".",
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


def _owner_is_estate(owner: str) -> bool:
    if _ESTATE_RE.search(owner):
        return True
    if not _TRAILING_ESTATE_RE.search(owner) or _REAL_ESTATE_RE.search(owner):
        return False
    return not _BUSINESS_ENTITY_RE.search(owner)


def _title_flags(title: TitleSignal) -> list[RiskFlag]:
    owner = (title.owner or "").upper()
    if not owner:
        return []
    flags: list[RiskFlag] = []
    if _owner_is_estate(owner):
        flags.append(
            RiskFlag(
                "estate_owner",
                "medium",
                "Estate / deceased owner",
                "Owner of record appears to be an estate or deceased owner; expect probate or "
                "title-clearing before a clean conveyance.",
                "parcel",
            )
        )
    if _MULTIPLE_OWNERS_RE.search(owner):
        flags.append(
            RiskFlag(
                "multiple_owners",
                "low",
                "Additional owners on record",
                "Owner of record lists unnamed additional parties (et al/et ux); confirm every "
                "owner is on the deed for a clean title.",
                "parcel",
            )
        )
    return flags


def _access_flag(access: AccessSignal) -> RiskFlag | None:
    if not access.has_geometry or access.has_street_frontage:
        return None
    return RiskFlag(
        "no_street_access",
        "low",
        "No street frontage detected",
        f"No mapped street within {STREET_ACCESS_MAX_FT:.0f} ft of the parcel; it may be "
        "landlocked. Confirm street access, a right-of-way, or an easement before assuming "
        "by-right development.",
        "street_centerline",
    )


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
    if signals.title is not None:
        flags.extend(_title_flags(signals.title))
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
    if signals.access is not None:
        access_flag = _access_flag(signals.access)
        if access_flag is not None:
            flags.append(access_flag)

    risk_score = min(100.0, sum(_WEIGHT[flag.severity] for flag in flags))
    confidence: Confidence = "high" if signals.tax is not None else "medium"
    return RiskAssessment(
        risk_score=risk_score,
        flags=flags,
        summary=_summarize(flags),
        confidence=confidence,
    )
