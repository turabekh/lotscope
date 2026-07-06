from typing import Any

from lotscope.checklist.schemas import ChecklistItem, ChecklistStatus, ChecklistSummary
from lotscope.markets.capabilities import (
    checklist_category_state,
    checklist_state_detail,
    clear_detail_override,
)
from lotscope.verdict.schemas import VerdictResult

_SEVERITY_STATUS: dict[str, ChecklistStatus] = {
    "high": "fail",
    "medium": "warn",
    "low": "info",
    "info": "info",
}
_STATUS_RANK: dict[ChecklistStatus, int] = {"pass": 0, "info": 1, "warn": 2, "fail": 3}

_RISK_CATEGORIES: list[tuple[str, str, frozenset[str], str]] = [
    (
        "liens_taxes",
        "Liens & taxes",
        frozenset({"tax_delinquency", "sheriff_sale"}),
        "No tax delinquency, liens, or sheriff-sale exposure on record.",
    ),
    (
        "li",
        "L&I & demolition",
        frozenset({"imminently_dangerous", "unsafe_structure", "li_violations", "demolition"}),
        "No L&I violations, unsafe or dangerous flags, or demolitions on record.",
    ),
    (
        "flood",
        "Flood & environmental",
        frozenset({"flood_zone"}),
        "Not in a mapped FEMA flood zone.",
    ),
    (
        "access",
        "Access & frontage",
        frozenset({"no_street_access"}),
        "Street frontage detected; the lot is not landlocked.",
    ),
    (
        "ownership",
        "Ownership & title",
        frozenset({"public_ownership", "estate_owner", "multiple_owners"}),
        "Privately held with no public-ownership or title-cloud flags on the owner record.",
    ),
    (
        "overlays",
        "Historic & overlays",
        frozenset({"historic_district", "overlay_district", "rco"}),
        "Not in a historic district, zoning overlay, or RCO; no extra design review or "
        "community-meeting requirement.",
    ),
]


def _worse(current: ChecklistStatus, candidate: ChecklistStatus) -> ChecklistStatus:
    return current if _STATUS_RANK[current] >= _STATUS_RANK[candidate] else candidate


def _risk_item(
    code: str,
    category: str,
    flag_codes: frozenset[str],
    clear_detail: str,
    flags: list[Any],
    *,
    availability: str = "available",
    state_detail: str = "",
) -> ChecklistItem:
    if availability != "available":
        return ChecklistItem(
            code=code,
            category=category,
            status="info",
            detail=state_detail,
            availability=availability,
        )
    matched = [flag for flag in flags if flag.get("code") in flag_codes]
    if not matched:
        return ChecklistItem(code=code, category=category, status="pass", detail=clear_detail)
    status: ChecklistStatus = "info"
    details: list[str] = []
    sources: set[str] = set()
    for flag in matched:
        status = _worse(status, _SEVERITY_STATUS.get(str(flag.get("severity", "info")), "info"))
        detail = str(flag.get("detail") or flag.get("label") or "")
        if detail:
            details.append(detail)
        if flag.get("source"):
            sources.add(str(flag.get("source")))
    return ChecklistItem(
        code=code,
        category=category,
        status=status,
        detail=" ".join(details),
        source=", ".join(sorted(sources)) or None,
    )


def _abatement_item() -> ChecklistItem:
    return ChecklistItem(
        code="abatement",
        category="Liens & taxes",
        status="info",
        detail=(
            "An OPA tax exemption is recorded (possible active abatement) — confirm the "
            "remaining abatement term with OPA before underwriting carrying costs."
        ),
        source="opa_properties_public",
    )


def _zoning_item(verdict: VerdictResult) -> ChecklistItem:
    if verdict.can_build_by_right:
        units = verdict.by_right_units
        suffix = f" ({units} unit(s))" if units else ""
        return ChecklistItem(
            code="zoning",
            category="Zoning & buildability",
            status="pass",
            detail=f"Buildable by-right{suffix} under the resolved district.",
            source="zoning",
        )
    if verdict.needs_variance:
        return ChecklistItem(
            code="zoning",
            category="Zoning & buildability",
            status="warn",
            detail="A variance or special exception is likely required to build.",
            source="zoning",
        )
    return ChecklistItem(
        code="zoning",
        category="Zoning & buildability",
        status="info",
        detail="Zoning conformance could not be determined for this parcel.",
        source="zoning",
    )


def _valuation_item(verdict: VerdictResult) -> ChecklistItem:
    if verdict.value_estimate_low is None or verdict.value_estimate_high is None:
        return ChecklistItem(
            code="valuation",
            category="Valuation confidence",
            status="warn",
            detail="Not enough comparable sales for a confident value estimate.",
            source="valuation",
        )
    if verdict.value_confidence is not None and verdict.value_confidence >= 0.6:
        return ChecklistItem(
            code="valuation",
            category="Valuation confidence",
            status="pass",
            detail=(
                f"Comparable sales support an estimate of "
                f"${verdict.value_estimate_low:,.0f}-${verdict.value_estimate_high:,.0f}."
            ),
            source="valuation",
        )
    return ChecklistItem(
        code="valuation",
        category="Valuation confidence",
        status="warn",
        detail="Value estimate rests on thin or dispersed comps; treat it as low-confidence.",
        source="valuation",
    )


def _deal_item(verdict: VerdictResult) -> ChecklistItem:
    if verdict.max_allowable_offer is None:
        return ChecklistItem(
            code="deal",
            category="Deal feasibility",
            status="info",
            detail="Not enough zoning or comp data to model the deal.",
            source="deal",
        )
    if verdict.is_underpriced:
        return ChecklistItem(
            code="deal",
            category="Deal feasibility",
            status="pass",
            detail=(
                f"Acquisition sits at or below the max allowable offer "
                f"(${verdict.max_allowable_offer:,.0f})."
            ),
            source="deal",
        )
    if verdict.est_margin is not None and verdict.est_margin < 0:
        return ChecklistItem(
            code="deal",
            category="Deal feasibility",
            status="warn",
            detail="Project does not pencil at the modeled costs and ARV.",
            source="deal",
        )
    return ChecklistItem(
        code="deal",
        category="Deal feasibility",
        status="info",
        detail=f"Max allowable offer ${verdict.max_allowable_offer:,.0f} at the target margin.",
        source="deal",
    )


def build_checklist(
    verdict: VerdictResult,
    *,
    has_abatement: bool = False,
    market_code: str = "phl",
) -> tuple[list[ChecklistItem], ChecklistSummary]:
    flags = verdict.risk_flags
    items = [_zoning_item(verdict)]
    for code, category, flag_codes, clear_detail in _RISK_CATEGORIES:
        state = checklist_category_state(market_code, code)
        clear = clear_detail_override(market_code, code) or clear_detail
        items.append(
            _risk_item(
                code,
                category,
                flag_codes,
                clear,
                flags,
                availability=state,
                state_detail=checklist_state_detail(market_code, code, state),
            )
        )
    if has_abatement:
        items.append(_abatement_item())
    items.append(_valuation_item(verdict))
    items.append(_deal_item(verdict))

    summary = ChecklistSummary(
        passed=sum(1 for item in items if item.status == "pass"),
        warnings=sum(1 for item in items if item.status == "warn"),
        failures=sum(1 for item in items if item.status == "fail"),
        info=sum(1 for item in items if item.status == "info"),
        ready=not any(item.status == "fail" for item in items),
    )
    return items, summary
