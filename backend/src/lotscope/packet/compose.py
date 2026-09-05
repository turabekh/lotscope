from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from lotscope.buybox.schemas import BuyBoxRead
from lotscope.deal.sensitivity import SensitivityGrid
from lotscope.packet.schemas import (
    VERIFY_BEFORE_BIDDING,
    DataAsOf,
    LotVerdict,
    PacketComp,
    PacketHeader,
    PacketLot,
    PacketModel,
    PassedLot,
    RedFlag,
    SensitiveInput,
)
from lotscope.risk.service import NOT_SCHEDULED_STATUSES
from lotscope.zoning.codes import normalize_zoning_code

OPA_URL = "https://opendataphilly.org/datasets/philadelphia-properties-and-assessments/"
LI_URL = "https://opendataphilly.org/datasets/licenses-and-inspections-violations/"
TAX_URL = "https://opendataphilly.org/datasets/real-estate-tax-delinquencies/"
RTT_URL = "https://opendataphilly.org/datasets/real-estate-transfers/"
FLOOD_URL = "https://msc.fema.gov/portal/home"
HISTORIC_URL = "https://opendataphilly.org/datasets/philadelphia-historic-districts/"
ZONING_URL = "https://opendataphilly.org/datasets/zoning-base-districts/"
SHERIFF_URL = "https://philadelphia.sheriffsale.com/"
LANDBANK_URL = "https://phdcphila.org/land/buy-land/"

_MARGIN_LOOK_BAND = 0.05


@dataclass(frozen=True)
class LotInputs:
    parcel_number: str
    address: str | None = None
    case_number: str | None = None
    sale_type: str | None = None
    sale_date: date | None = None
    opening_bid: float | None = None
    status: str | None = None
    plaintiff: str | None = None

    is_vacant: bool = False
    lot_area_sqft: float | None = None
    zoning_code: str | None = None
    overlays: tuple[str, ...] = ()

    can_build_by_right: bool | None = None
    by_right_units: int | None = None
    dimensional_reason: str | None = None
    provision_id: str | None = None

    max_allowable_offer: float | None = None
    est_margin: float | None = None
    sensitivity: SensitivityGrid | None = None

    open_violation_count: int = 0
    most_recent_violation: date | None = None
    has_unsafe_structure: bool = False
    is_delinquent: bool = False
    total_due: float | None = None
    delinquency_owner: str | None = None
    city_neighbor: bool = False
    in_historic_district: bool = False
    in_flood_zone: bool = False

    comps: tuple[PacketComp, ...] = ()

    sources_fetched_at: dict[str, datetime] = field(default_factory=dict)


def is_scheduled(status: str | None, sale_date: date | None, today: date) -> bool:
    if sale_date is None or sale_date < today:
        return False
    return (status or "") not in NOT_SCHEDULED_STATUSES


def _flag(
    code: str,
    label: str,
    detail: str,
    severity: Literal["high", "medium", "low"],
    source: str,
    url: str,
    fetched: dict[str, datetime],
) -> RedFlag:
    return RedFlag(
        code=code,
        label=label,
        detail=detail,
        severity=severity,
        source=source,
        source_url=url,
        fetched_at=fetched.get(source),
    )


def red_flags(lot: LotInputs) -> list[RedFlag]:
    flags: list[RedFlag] = []
    fetched = lot.sources_fetched_at

    if lot.open_violation_count > 0:
        recent = (
            f" Most recent {lot.most_recent_violation.isoformat()}."
            if lot.most_recent_violation is not None
            else ""
        )
        flags.append(
            _flag(
                "open_violations",
                "Open L&I violations",
                f"{lot.open_violation_count} open violation"
                f"{'' if lot.open_violation_count == 1 else 's'}.{recent}",
                "medium",
                "li_event",
                LI_URL,
                fetched,
            )
        )

    if lot.has_unsafe_structure:
        flags.append(
            _flag(
                "unsafe_structure",
                "Unsafe or imminently dangerous structure",
                "L&I records an unsafe or imminently dangerous structure on or beside this lot.",
                "high",
                "li_event",
                LI_URL,
                fetched,
            )
        )

    if lot.is_delinquent:
        owed = f"${lot.total_due:,.0f}" if lot.total_due is not None else "an unstated amount"
        debtor = lot.delinquency_owner or "an unnamed party"
        flags.append(
            _flag(
                "tax_delinquent",
                "Tax delinquency",
                f"{owed} owed, recorded against {debtor}.",
                "high",
                "tax_status",
                TAX_URL,
                fetched,
            )
        )

    if lot.city_neighbor:
        flags.append(
            _flag(
                "city_neighbor",
                "City, PHA or Land Bank neighbour",
                "A neighbouring parcel is publicly held, which can help an assemblage "
                "or complicate access.",
                "low",
                "parcel",
                LANDBANK_URL,
                fetched,
            )
        )

    if lot.in_historic_district:
        flags.append(
            _flag(
                "historic",
                "Historic district",
                "Every permit goes through Historical Commission review.",
                "medium",
                "historicdistricts_local",
                HISTORIC_URL,
                fetched,
            )
        )

    if lot.in_flood_zone:
        flags.append(
            _flag(
                "flood",
                "Special Flood Hazard Area",
                "Flood insurance and elevated construction apply.",
                "high",
                "flood_zone",
                FLOOD_URL,
                fetched,
            )
        )

    for overlay in lot.overlays:
        flags.append(
            _flag(
                "overlay",
                f"Overlay: {overlay}",
                f"{overlay} modifies the base district's standards.",
                "low",
                "zoning_overlays",
                ZONING_URL,
                fetched,
            )
        )

    return flags


def sensitive_inputs(grid: SensitivityGrid | None) -> list[SensitiveInput]:
    if grid is None or not grid.available:
        return []
    margins = [cell.margin for cell in grid.cells if cell.margin is not None]
    if len(margins) < 2:
        return []
    exit_swing = _swing(grid, "exit_multiplier")
    cost_swing = _swing(grid, "cost_multiplier")
    candidates = [
        SensitiveInput(
            name=grid.row_label,
            detail=f"Moving {grid.row_label.lower()} across the tested range swings the margin "
            f"by {exit_swing:.1%}.",
            swing=exit_swing,
        ),
        SensitiveInput(
            name=grid.column_label,
            detail=f"Moving {grid.column_label.lower()} across the tested range swings the margin "
            f"by {cost_swing:.1%}.",
            swing=cost_swing,
        ),
    ]
    return sorted(candidates, key=lambda item: item.swing, reverse=True)[:2]


def _swing(grid: SensitivityGrid, axis: str) -> float:
    by_axis: dict[float, list[float]] = {}
    for cell in grid.cells:
        if cell.margin is None:
            continue
        by_axis.setdefault(getattr(cell, axis), []).append(cell.margin)
    means = [sum(values) / len(values) for values in by_axis.values() if values]
    return max(means) - min(means) if len(means) >= 2 else 0.0


def _buy_box_exclusion(lot: LotInputs, buy_box: BuyBoxRead) -> str | None:
    if buy_box.exclude_historic and lot.in_historic_district:
        return "In a historic district, which your buy box excludes."
    if buy_box.exclude_flood and lot.in_flood_zone:
        return "In a Special Flood Hazard Area, which your buy box excludes."
    if buy_box.exclude_open_violations and lot.open_violation_count > 0:
        return f"{lot.open_violation_count} open L&I violations, which your buy box excludes."
    if buy_box.exclude_city_neighbor and lot.city_neighbor:
        return "Has a publicly held neighbour, which your buy box excludes."
    if (
        buy_box.min_lot_sqft is not None
        and lot.lot_area_sqft is not None
        and lot.lot_area_sqft < buy_box.min_lot_sqft
    ):
        return f"{lot.lot_area_sqft:,.0f} sqft is below your {buy_box.min_lot_sqft:,} sqft floor."
    if buy_box.zoning_codes and lot.zoning_code is not None:
        allowed = {normalize_zoning_code(code) for code in buy_box.zoning_codes}
        if normalize_zoning_code(lot.zoning_code) not in allowed:
            return f"{lot.zoning_code} is not one of your districts."
    return None


def decide(lot: LotInputs, buy_box: BuyBoxRead, required_margin: float) -> tuple[LotVerdict, str]:
    excluded = _buy_box_exclusion(lot, buy_box)
    if excluded is not None:
        return "PASS", excluded

    if lot.can_build_by_right is False:
        return (
            "PASS",
            "Nothing can be built by right, so the lot needs a variance to be worth a bid.",
        )

    if lot.max_allowable_offer is None or lot.est_margin is None:
        return (
            "LOOK",
            "No offer could be computed from the data we hold, so this one needs a manual read.",
        )

    if buy_box.max_bid is not None and lot.max_allowable_offer > buy_box.max_bid:
        return (
            "PASS",
            f"The most this lot supports is ${lot.max_allowable_offer:,.0f}, above your "
            f"${buy_box.max_bid:,.0f} ceiling.",
        )

    if lot.opening_bid is not None and lot.opening_bid > lot.max_allowable_offer:
        return (
            "PASS",
            f"The opening bid of ${lot.opening_bid:,.0f} already exceeds the "
            f"${lot.max_allowable_offer:,.0f} this lot supports.",
        )

    if lot.est_margin < required_margin - _MARGIN_LOOK_BAND:
        return (
            "PASS",
            f"Estimated margin {lot.est_margin:.1%} is well under your "
            f"{required_margin:.1%} target.",
        )

    if lot.est_margin < required_margin:
        return (
            "LOOK",
            f"Estimated margin {lot.est_margin:.1%} is just under your "
            f"{required_margin:.1%} target, so it turns on the assumptions.",
        )

    high_flags = [flag for flag in red_flags(lot) if flag.severity == "high"]
    if high_flags:
        blocker = high_flags[0].label.lower()
        return (
            "LOOK",
            f"The numbers work at ${lot.max_allowable_offer:,.0f}, "
            f"but {blocker} needs clearing first.",
        )

    return (
        "BID",
        f"Supports ${lot.max_allowable_offer:,.0f} at {lot.est_margin:.1%} margin, "
        f"inside your ceiling and clear of your exclusions.",
    )


def _to_lot(lot: LotInputs, buy_box: BuyBoxRead, required_margin: float, today: date) -> PacketLot:
    verdict, reason = decide(lot, buy_box, required_margin)
    comps = list(lot.comps)
    prices = [comp.sale_price for comp in comps if comp.sale_price is not None]
    return PacketLot(
        parcel_number=lot.parcel_number,
        address=lot.address,
        case_number=lot.case_number,
        sale_type=lot.sale_type,
        opening_bid=lot.opening_bid,
        status=lot.status,
        is_scheduled=is_scheduled(lot.status, lot.sale_date, today),
        plaintiff=lot.plaintiff,
        is_vacant=lot.is_vacant,
        lot_area_sqft=lot.lot_area_sqft,
        zoning_code=lot.zoning_code,
        overlays=list(lot.overlays),
        can_build_by_right=lot.can_build_by_right,
        by_right_units=lot.by_right_units,
        dimensional_reason=lot.dimensional_reason,
        provision_id=lot.provision_id,
        max_allowable_offer=lot.max_allowable_offer,
        est_margin=lot.est_margin,
        sensitive_inputs=sensitive_inputs(lot.sensitivity),
        red_flags=red_flags(lot),
        comps=comps,
        comp_range_low=min(prices) if prices else None,
        comp_range_high=max(prices) if prices else None,
        verdict=verdict,
        verdict_reason=reason,
        verify_before_bidding=list(VERIFY_BEFORE_BIDDING),
    )


def compose_packet(
    *,
    sale_date: date,
    buy_box: BuyBoxRead,
    required_margin: float,
    lots: list[LotInputs],
    data_as_of: list[DataAsOf],
    generated_at: datetime,
    today: date | None = None,
) -> PacketModel:
    as_of_today = today or generated_at.date()
    vacant = [lot for lot in lots if lot.is_vacant]
    non_vacant = [lot for lot in lots if not lot.is_vacant]

    composed = [_to_lot(lot, buy_box, required_margin, as_of_today) for lot in vacant]
    kept = [lot for lot in composed if lot.verdict != "PASS"]
    passed = [
        PassedLot(parcel_number=lot.parcel_number, address=lot.address, reason=lot.verdict_reason)
        for lot in composed
        if lot.verdict == "PASS"
    ]

    kept.sort(
        key=lambda lot: (
            0 if lot.verdict == "BID" else 1,
            -(lot.est_margin or -1.0),
            lot.parcel_number,
        )
    )

    sale_types = sorted({lot.sale_type for lot in lots if lot.sale_type})
    header = PacketHeader(
        sale_date=sale_date,
        sale_types=sale_types,
        listings=len(lots),
        vacant=len(vacant),
        passing_buy_box=len(kept),
        generated_at=generated_at,
        data_as_of=data_as_of,
    )
    return PacketModel(
        header=header,
        lots=kept,
        passed=passed,
        non_vacant_appendix=[
            PassedLot(
                parcel_number=lot.parcel_number,
                address=lot.address,
                reason="Not a vacant lot, so it is outside what this packet screens.",
            )
            for lot in non_vacant
        ],
        buy_box_summary=_buy_box_summary(buy_box, required_margin),
    )


def _buy_box_summary(buy_box: BuyBoxRead, required_margin: float) -> dict[str, Any]:
    return {
        "max_bid": buy_box.max_bid,
        "target_use": buy_box.target_use,
        "min_lot_sqft": buy_box.min_lot_sqft,
        "zoning_codes": list(buy_box.zoning_codes),
        "required_margin": required_margin,
        "exclude_historic": buy_box.exclude_historic,
        "exclude_flood": buy_box.exclude_flood,
        "exclude_open_violations": buy_box.exclude_open_violations,
        "exclude_city_neighbor": buy_box.exclude_city_neighbor,
    }
