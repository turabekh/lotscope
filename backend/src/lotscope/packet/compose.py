from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from lotscope.buybox.schemas import BuyBoxRead
from lotscope.deal.sensitivity import SensitivityGrid
from lotscope.packet.schemas import (
    VERIFY_BEFORE_BIDDING,
    AdjacentParcel,
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

    clearing_estimate: float | None = None
    clearing_sample_size: int = 0
    clearing_low: float | None = None
    clearing_high: float | None = None
    clearing_sufficient: bool = False
    clearing_reason: str | None = None
    clearing_source: str | None = None
    clearing_source_url: str | None = None

    adjacent: tuple[AdjacentParcel, ...] = ()
    variance_needed: str | None = None
    variance_outlook_favourable: bool | None = None
    variance_outlook_basis: str | None = None

    computed_at: datetime | None = None
    sources_fetched_at: dict[str, datetime] = field(default_factory=dict)

    @property
    def comp_prices(self) -> list[float]:
        return [comp.sale_price for comp in self.comps if comp.sale_price is not None]

    @property
    def comp_low(self) -> float | None:
        prices = self.comp_prices
        return min(prices) if prices else None

    @property
    def comp_high(self) -> float | None:
        prices = self.comp_prices
        return max(prices) if prices else None


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


def _buy_box_exclusion(lot: LotInputs, buy_box: BuyBoxRead, use: str) -> str | None:
    if buy_box.exclude_historic and lot.in_historic_district:
        return "In a historic district, which your buy box excludes."
    if buy_box.exclude_flood and lot.in_flood_zone:
        return "In a Special Flood Hazard Area, which your buy box excludes."
    if buy_box.exclude_open_violations and lot.open_violation_count > 0:
        return f"{lot.open_violation_count} open L&I violations, which your buy box excludes."
    if buy_box.exclude_city_neighbor and lot.city_neighbor:
        return "Has a publicly held neighbour, which your buy box excludes."
    if (
        use != "assemble"
        and buy_box.min_lot_sqft is not None
        and lot.lot_area_sqft is not None
        and lot.lot_area_sqft < buy_box.min_lot_sqft
    ):
        return f"{lot.lot_area_sqft:,.0f} sqft is below your {buy_box.min_lot_sqft:,} sqft floor."
    if buy_box.zoning_codes and lot.zoning_code is not None:
        allowed = {normalize_zoning_code(code) for code in buy_box.zoning_codes}
        if normalize_zoning_code(lot.zoning_code) not in allowed:
            return f"{lot.zoning_code} is not one of your districts."
    return None


def _blocking_flag(lot: LotInputs, buy_box: BuyBoxRead) -> str | None:
    if lot.has_unsafe_structure:
        return (
            "L&I records an unsafe or imminently dangerous structure on or beside this lot, "
            "which stops any lens."
        )
    if buy_box.exclude_historic and lot.in_historic_district:
        return "In a historic district, which your buy box excludes."
    if buy_box.exclude_flood and lot.in_flood_zone:
        return "In a Special Flood Hazard Area, which your buy box excludes."
    return None


def _grade_build(
    lot: LotInputs, buy_box: BuyBoxRead, required_margin: float
) -> tuple[LotVerdict, str, str]:
    rule = "build"
    if lot.can_build_by_right is True:
        if lot.max_allowable_offer is None or lot.est_margin is None:
            return (
                "LOOK",
                "By-right eligible, but no offer could be computed from the data we hold.",
                f"{rule}: by-right eligible, offer not computable",
            )
        if lot.opening_bid is not None and lot.max_allowable_offer < lot.opening_bid:
            return (
                "LOOK",
                f"By-right eligible, but the ${lot.max_allowable_offer:,.0f} it supports is "
                f"under the ${lot.opening_bid:,.0f} opening bid.",
                f"{rule}: by-right eligible, MAO below opening bid",
            )
        if lot.est_margin < required_margin:
            return (
                "PASS",
                f"By-right eligible, but {lot.est_margin:.1%} margin is under your "
                f"{required_margin:.1%} target.",
                f"{rule}: by-right eligible, margin under target",
            )
        if buy_box.max_bid is not None and lot.max_allowable_offer > buy_box.max_bid:
            return (
                "PASS",
                f"Supports ${lot.max_allowable_offer:,.0f}, above your "
                f"${buy_box.max_bid:,.0f} ceiling.",
                f"{rule}: MAO above your max bid",
            )
        return (
            "BID",
            f"By-right eligible, supports ${lot.max_allowable_offer:,.0f} against a "
            f"${lot.opening_bid:,.0f} opening bid at {lot.est_margin:.1%} margin."
            if lot.opening_bid is not None
            else f"By-right eligible, supports ${lot.max_allowable_offer:,.0f} at "
            f"{lot.est_margin:.1%} margin.",
            f"{rule}: by-right eligible, MAO >= opening bid, margin >= target",
        )

    if lot.variance_outlook_favourable is True:
        needed = lot.variance_needed or "a dimensional variance"
        basis = lot.variance_outlook_basis or "ZBA decisions for this district"
        return (
            "LOOK",
            f"Not buildable by right — needs {needed} — but the ZBA outlook is favourable "
            f"({basis}).",
            f"{rule}: variance needed, ZBA outlook favourable",
        )

    if lot.can_build_by_right is None:
        return (
            "LOOK",
            "Whether anything can be built by right could not be determined from the data we hold.",
            f"{rule}: by-right eligibility unknown",
        )

    needed = lot.variance_needed or "a variance"
    outlook_basis = lot.variance_outlook_basis
    tail = f" ZBA outlook: {outlook_basis}." if outlook_basis else ""
    return (
        "PASS",
        f"Not buildable by right — needs {needed} — and the ZBA outlook does not support it.{tail}",
        f"{rule}: variance needed, ZBA outlook not favourable",
    )


def _adjacency_summary(lot: LotInputs) -> str:
    parts = [
        f"{item.parcel_number}{f' ({item.address})' if item.address else ''} [{item.owner_class}]"
        for item in lot.adjacent
    ]
    return ", ".join(parts)


def _combined_footprint_sqft(lot: LotInputs) -> float | None:
    if lot.lot_area_sqft is None:
        return None
    extra = sum(item.lot_area_sqft or 0.0 for item in lot.adjacent)
    return lot.lot_area_sqft + extra


def _grade_assemble(lot: LotInputs, buy_box: BuyBoxRead) -> tuple[LotVerdict, str, str]:
    rule = "assemble"
    if not lot.adjacent:
        return (
            "PASS",
            "No adjacent vacant, publicly held or already-owned parcel shares a boundary.",
            f"{rule}: no qualifying adjacent parcel",
        )

    named = _adjacency_summary(lot)
    combined = _combined_footprint_sqft(lot)
    floor = buy_box.min_lot_sqft
    if combined is not None and floor is not None and combined >= floor:
        return (
            "BID",
            f"Combined with {named} the footprint reaches {combined:,.0f} sqft, at or above "
            f"your {floor:,} sqft floor.",
            f"{rule}: combined footprint by-right buildable under your floor",
        )
    if combined is not None and floor is not None:
        return (
            "LOOK",
            f"Adjacent to {named}, but the combined {combined:,.0f} sqft is still under "
            f"your {floor:,} sqft floor.",
            f"{rule}: adjacent, combined footprint under your floor",
        )
    return (
        "LOOK",
        f"Adjacent to {named}, but the combined footprint could not be measured.",
        f"{rule}: adjacent, combined footprint unknown",
    )


def _grade_resale(lot: LotInputs, buy_box: BuyBoxRead) -> tuple[LotVerdict, str, str]:
    rule = "hold/flip"
    low = lot.comp_low
    if low is None:
        return (
            "LOOK",
            "No comparable land sale nearby, so a resale spread cannot be measured.",
            f"{rule}: no comparable range",
        )

    if not lot.clearing_sufficient or lot.clearing_estimate is None:
        return (
            "LOOK",
            f"Not enough recent sheriff clearing data nearby "
            f"(n={lot.clearing_sample_size}), so what this lot will actually cost is unknown.",
            f"{rule}: clearing estimate insufficient",
        )

    clearing = lot.clearing_estimate
    threshold = low * buy_box.flip_bid_ratio
    if lot.clearing_low is not None and lot.clearing_high is not None:
        band = f", ${lot.clearing_low:,.0f}-${lot.clearing_high:,.0f}"
    else:
        band = ""
    spread = (
        f"Expected clearing ${clearing:,.0f} (median of {lot.clearing_sample_size} nearby "
        f"sheriff's deeds{band})"
    )
    if clearing <= threshold:
        return (
            "BID",
            f"{spread} is at or under {buy_box.flip_bid_ratio:.0%} of the ${low:,.0f} "
            f"comp low (${threshold:,.0f}).",
            f"{rule}: clearing estimate <= {buy_box.flip_bid_ratio:.0%} of comp low",
        )
    if clearing <= low:
        return (
            "LOOK",
            f"{spread} is under the ${low:,.0f} comp low but above "
            f"{buy_box.flip_bid_ratio:.0%} of it.",
            f"{rule}: clearing estimate <= comp low",
        )
    return (
        "PASS",
        f"{spread} is already at or above the ${low:,.0f} comp low.",
        f"{rule}: clearing estimate above comp low",
    )


_LENS_LABEL = {
    "build": "build",
    "assemble": "assemble",
    "hold": "hold/flip",
    "flip": "hold/flip",
}


def _grade_for(
    use: str, lot: LotInputs, buy_box: BuyBoxRead, required_margin: float
) -> tuple[LotVerdict, str, str]:
    if use == "build":
        return _grade_build(lot, buy_box, required_margin)
    if use == "assemble":
        return _grade_assemble(lot, buy_box)
    return _grade_resale(lot, buy_box)


def decide(
    lot: LotInputs, buy_box: BuyBoxRead, required_margin: float
) -> tuple[LotVerdict, str, str, list[str]]:
    blocking = _blocking_flag(lot, buy_box)
    if blocking is not None:
        return "PASS", blocking, "all lenses: blocking red flag", []

    use = buy_box.target_use
    excluded = _buy_box_exclusion(lot, buy_box, use)
    if excluded is not None:
        return "PASS", excluded, f"{_LENS_LABEL[use]}: outside your buy box", []

    verdict, reason, rule = _grade_for(use, lot, buy_box, required_margin)

    also: list[str] = []
    for other in ("build", "assemble", "hold"):
        if other == use or (other == "hold" and use == "flip"):
            continue
        other_excluded = _buy_box_exclusion(lot, buy_box, other)
        if other_excluded is not None:
            also.append(f"also as {_LENS_LABEL[other]}: PASS - {other_excluded}")
            continue
        other_verdict, other_reason, _ = _grade_for(other, lot, buy_box, required_margin)
        also.append(f"also as {_LENS_LABEL[other]}: {other_verdict} - {other_reason}")
    return verdict, reason, rule, also


def _to_lot(
    lot: LotInputs,
    buy_box: BuyBoxRead,
    required_margin: float,
    today: date,
    generated_at: datetime,
) -> PacketLot:
    verdict, reason, rule, also = decide(lot, buy_box, required_margin)
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
        comps=list(lot.comps),
        comp_range_low=lot.comp_low,
        comp_range_high=lot.comp_high,
        clearing_estimate=lot.clearing_estimate,
        clearing_sample_size=lot.clearing_sample_size,
        clearing_low=lot.clearing_low,
        clearing_high=lot.clearing_high,
        clearing_sufficient=lot.clearing_sufficient,
        clearing_reason=lot.clearing_reason,
        clearing_source=lot.clearing_source,
        clearing_source_url=lot.clearing_source_url,
        adjacent=list(lot.adjacent),
        variance_needed=lot.variance_needed,
        variance_outlook=lot.variance_outlook_basis,
        verdict=verdict,
        verdict_reason=reason,
        graded_as=buy_box.target_use,
        grade_rule=rule,
        also=also,
        computed_at=lot.computed_at or generated_at,
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

    composed = [_to_lot(lot, buy_box, required_margin, as_of_today, generated_at) for lot in vacant]
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
        target_use=buy_box.target_use,
        computed_at=generated_at,
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
        "flip_bid_ratio": buy_box.flip_bid_ratio,
        "exclude_historic": buy_box.exclude_historic,
        "exclude_flood": buy_box.exclude_flood,
        "exclude_open_violations": buy_box.exclude_open_violations,
        "exclude_city_neighbor": buy_box.exclude_city_neighbor,
    }
