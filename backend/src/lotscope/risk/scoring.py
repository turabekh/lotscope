import re
from dataclasses import dataclass, field
from typing import Literal

from lotscope.risk.attribution import DelinquencyAttribution

Severity = Literal["high", "medium", "low", "info"]
Confidence = Literal["high", "medium", "low"]

_WEIGHT: dict[Severity, float] = {"high": 40.0, "medium": 20.0, "low": 10.0, "info": 0.0}
_SFHA_ZONE_PREFIXES = ("A", "V")
_SFHA_HAZARD_MARKERS = ("100 YEAR", "1% ANNUAL", "1 PCT ANNUAL")
_MODERATE_HAZARD_MARKERS = ("0.2", "SHADED", "500 YEAR")
_MINIMAL_HAZARD_MARKERS = ("MINIMAL", "OPEN WATER")
_LEGACY_MODERATE_ZONE = "B"
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
    attribution: DelinquencyAttribution | None = None


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
    street_data_available: bool = True


@dataclass(frozen=True)
class HistoricSignal:
    in_district: bool
    district_name: str | None = None


@dataclass(frozen=True)
class OverlaySignal:
    overlay_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class RcoSignal:
    rco_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class RiskSignals:
    li: LiSignal
    tax: TaxSignal | None = None
    is_city_owned: bool | None = None
    flood_zones: list[str] = field(default_factory=list)
    title: TitleSignal | None = None
    access: AccessSignal | None = None
    historic: HistoricSignal | None = None
    overlays: OverlaySignal | None = None
    rco: RcoSignal | None = None


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
        due = tax.total_due
        detail = f"${due:,.0f} owed" if due is not None else "Amount owed not reported"
        if tax.years_owed:
            detail += f" over {tax.years_owed} year(s)"
        severity: Severity = (
            "high"
            if (due is not None and due >= _TAX_HIGH_DUE)
            or (tax.years_owed or 0) >= _TAX_HIGH_YEARS
            else "medium"
        )
        title = "Tax delinquency"
        if tax.attribution is not None:
            detail += f". {tax.attribution.note}"
            if tax.attribution.posture == "likely_discharged":
                severity = "info"
                title = "Tax delinquency recorded against a prior owner"
            elif tax.attribution.posture == "verify":
                severity = "medium"
        else:
            detail += "."
        flags.append(RiskFlag("tax_delinquency", severity, title, detail, "tax_status"))
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
    if not access.has_geometry or access.has_street_frontage or not access.street_data_available:
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


_HISTORIC_REVIEW_BODY: dict[str, str] = {
    "phl": "Philadelphia Historical Commission",
    "wlm": "Wilmington Historic Preservation Commission",
}
_OVERLAY_CITATION: dict[str, str] = {
    "phl": "Title 14 §14-500 series",
    "wlm": "Wilmington Zoning Code (Ch. 48)",
}


def _historic_flag(historic: HistoricSignal, market_code: str = "phl") -> RiskFlag | None:
    if not historic.in_district:
        return None
    where = f"the {historic.district_name} historic district" if historic.district_name else "a"
    article = "" if historic.district_name else " local historic district"
    body = _HISTORIC_REVIEW_BODY.get(market_code, "the local historic commission")
    return RiskFlag(
        "historic_district",
        "low",
        "Historic district overlay",
        f"Parcel sits in {where}{article}; exterior alterations, demolition, and new "
        f"construction require {body} review, adding time and cost.",
        "historicdistricts_local",
    )


def _overlay_flag(overlays: OverlaySignal, market_code: str = "phl") -> RiskFlag | None:
    if not overlays.overlay_names:
        return None
    names = ", ".join(overlays.overlay_names)
    citation = _OVERLAY_CITATION.get(market_code, "the applicable zoning-overlay standards")
    return RiskFlag(
        "overlay_district",
        "low",
        "Zoning overlay district",
        f"Parcel is in overlay {names} — check {citation} for modified "
        "standards that can change what is buildable by-right.",
        "zoning_overlays",
    )


def _rco_flag(rco: RcoSignal) -> RiskFlag | None:
    if not rco.rco_names:
        return None
    names = ", ".join(rco.rco_names)
    return RiskFlag(
        "rco",
        "low",
        "Registered Community Organization",
        f"RCO: {names} — a community meeting is required before a zoning variance or "
        "special exception.",
        "zoning_rco",
    )


def _classify_flood_zone(zone: str) -> Literal["sfha", "moderate", "minimal"]:
    normalized = zone.strip().upper()
    if any(marker in normalized for marker in _MINIMAL_HAZARD_MARKERS):
        return "minimal"
    if normalized == _LEGACY_MODERATE_ZONE or any(
        marker in normalized for marker in _MODERATE_HAZARD_MARKERS
    ):
        return "moderate"
    if normalized.startswith(_SFHA_ZONE_PREFIXES) or any(
        marker in normalized for marker in _SFHA_HAZARD_MARKERS
    ):
        return "sfha"
    return "minimal"


def _flood_flag(flood_zones: list[str]) -> RiskFlag | None:
    sfha_zones = [zone for zone in flood_zones if _classify_flood_zone(zone) == "sfha"]
    if sfha_zones:
        return RiskFlag(
            "flood_zone",
            "high",
            "FEMA flood zone",
            f"In a FEMA Special Flood Hazard Area (zone {', '.join(sfha_zones)}); "
            "flood insurance is typically required.",
            "flood_zone",
        )
    if any(_classify_flood_zone(zone) == "moderate" for zone in flood_zones):
        return RiskFlag(
            "flood_zone",
            "info",
            "FEMA flood zone",
            "0.2%-annual-chance flood zone — moderate hazard; verify stormwater and PWD "
            "requirements.",
            "flood_zone",
        )
    return None


def _summarize(flags: list[RiskFlag]) -> str:
    if not flags:
        return "No major risk flags found."
    severities = [flag.severity for flag in flags]
    for level in ("high", "medium", "low", "info"):
        if level in severities:
            return f"{len(flags)} risk flag(s); highest severity {level}."
    return f"{len(flags)} risk flag(s)."


def assess_risk(signals: RiskSignals, market_code: str = "phl") -> RiskAssessment:
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
    if signals.historic is not None:
        historic_flag = _historic_flag(signals.historic, market_code)
        if historic_flag is not None:
            flags.append(historic_flag)
    if signals.overlays is not None:
        overlay_flag = _overlay_flag(signals.overlays, market_code)
        if overlay_flag is not None:
            flags.append(overlay_flag)
    if signals.rco is not None:
        rco_flag = _rco_flag(signals.rco)
        if rco_flag is not None:
            flags.append(rco_flag)

    risk_score = min(100.0, sum(_WEIGHT[flag.severity] for flag in flags))
    confidence: Confidence = "high" if signals.tax is not None else "medium"
    return RiskAssessment(
        risk_score=risk_score,
        flags=flags,
        summary=_summarize(flags),
        confidence=confidence,
    )
