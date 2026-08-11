from dataclasses import dataclass, replace
from typing import Literal

LimitingFactor = Literal["area", "width", "both", "none"]


@dataclass(frozen=True)
class SmallLotProvision:
    trigger_lot_area_sqft: float
    min_child_lot_area_sqft: float
    min_lot_width_ft: float
    adjacent_small_share: float
    adjacent_small_max_area_sqft: float
    citation: str


SMALL_LOT_PROVISIONS: dict[str, SmallLotProvision] = {
    "RSA5": SmallLotProvision(
        trigger_lot_area_sqft=1600.0,
        min_child_lot_area_sqft=800.0,
        min_lot_width_ft=16.0,
        adjacent_small_share=0.75,
        adjacent_small_max_area_sqft=1000.0,
        citation="Title 14 \u00a714-701(2)(b)[2]",
    ),
    "RM1": SmallLotProvision(
        trigger_lot_area_sqft=1920.0,
        min_child_lot_area_sqft=960.0,
        min_lot_width_ft=16.0,
        adjacent_small_share=0.75,
        adjacent_small_max_area_sqft=1000.0,
        citation="Title 14 \u00a714-701(2)(c)[1]",
    ),
}


def small_lot_provision_for(district_code: str | None) -> SmallLotProvision | None:
    if district_code is None:
        return None
    key = district_code.upper().replace("-", "")
    return SMALL_LOT_PROVISIONS.get(key)


@dataclass(frozen=True)
class SubdivisionInputs:
    district_code: str | None
    lot_area_sqft: float | None
    lot_width_ft: float | None
    min_lot_area_sqft: float | None
    min_lot_width_ft: float | None
    small_lot_provision: SmallLotProvision | None = None
    adjacent_small_share: float | None = None
    has_overlay: bool = False


@dataclass(frozen=True)
class SubdivisionAnalysis:
    district_code: str | None
    can_subdivide: bool
    max_lots: int | None
    limiting_factor: LimitingFactor | None
    is_conforming: bool | None
    needs_consolidation: bool
    lot_area_sqft: float | None
    lot_width_ft: float | None
    min_lot_area_sqft: float | None
    min_lot_width_ft: float | None
    reasons: list[str]


def _lots_for(value: float | None, minimum: float | None) -> int | None:
    if value is None or minimum is None or minimum <= 0:
        return None
    return int(value // minimum)


def _limiting_factor(by_area: int | None, by_width: int | None) -> LimitingFactor:
    if by_area is None and by_width is None:
        return "none"
    if by_area is None:
        return "width"
    if by_width is None:
        return "area"
    if by_area < by_width:
        return "area"
    if by_width < by_area:
        return "width"
    return "both"


def _analyze_base(inputs: SubdivisionInputs) -> SubdivisionAnalysis:
    def result(
        *,
        can_subdivide: bool,
        max_lots: int | None,
        limiting_factor: LimitingFactor | None,
        is_conforming: bool | None,
        needs_consolidation: bool,
        reasons: list[str],
    ) -> SubdivisionAnalysis:
        return SubdivisionAnalysis(
            district_code=inputs.district_code,
            can_subdivide=can_subdivide,
            max_lots=max_lots,
            limiting_factor=limiting_factor,
            is_conforming=is_conforming,
            needs_consolidation=needs_consolidation,
            lot_area_sqft=inputs.lot_area_sqft,
            lot_width_ft=inputs.lot_width_ft,
            min_lot_area_sqft=inputs.min_lot_area_sqft,
            min_lot_width_ft=inputs.min_lot_width_ft,
            reasons=reasons,
        )

    if inputs.min_lot_area_sqft is None and inputs.min_lot_width_ft is None:
        return result(
            can_subdivide=False,
            max_lots=None,
            limiting_factor=None,
            is_conforming=None,
            needs_consolidation=False,
            reasons=["No dimensional minimums are recorded for this district."],
        )
    if inputs.lot_area_sqft is None and inputs.lot_width_ft is None:
        return result(
            can_subdivide=False,
            max_lots=None,
            limiting_factor=None,
            is_conforming=None,
            needs_consolidation=False,
            reasons=["Lot dimensions are unknown, so subdivision cannot be evaluated."],
        )

    by_area = _lots_for(inputs.lot_area_sqft, inputs.min_lot_area_sqft)
    by_width = _lots_for(inputs.lot_width_ft, inputs.min_lot_width_ft)
    counts = [count for count in (by_area, by_width) if count is not None]
    max_lots = min(counts) if counts else None
    limiting_factor = _limiting_factor(by_area, by_width)

    reasons: list[str] = []
    if max_lots is None:
        return result(
            can_subdivide=False,
            max_lots=None,
            limiting_factor=None,
            is_conforming=None,
            needs_consolidation=False,
            reasons=["Lot dimensions are incomplete for the recorded minimums."],
        )
    if max_lots >= 2:
        binding = {
            "area": "lot area",
            "width": "lot width",
            "both": "lot area and width",
            "none": "the recorded minimums",
        }[limiting_factor]
        reasons.append(
            f"Lot is large enough for up to {max_lots} conforming lots; {binding} is the "
            "binding constraint. Subdivision is subject to plan approval and access."
        )
        return result(
            can_subdivide=True,
            max_lots=max_lots,
            limiting_factor=limiting_factor,
            is_conforming=True,
            needs_consolidation=False,
            reasons=reasons,
        )
    if max_lots == 1:
        reasons.append("Lot meets the district minimums but is not large enough to split.")
        return result(
            can_subdivide=False,
            max_lots=1,
            limiting_factor=limiting_factor,
            is_conforming=True,
            needs_consolidation=False,
            reasons=reasons,
        )
    reasons.append(
        "Lot is below the district minimums; consolidating with an adjacent parcel may be "
        "needed to build by-right."
    )
    return result(
        can_subdivide=False,
        max_lots=0,
        limiting_factor=limiting_factor,
        is_conforming=False,
        needs_consolidation=True,
        reasons=reasons,
    )


def analyze_subdivision(inputs: SubdivisionInputs) -> SubdivisionAnalysis:
    base = _analyze_base(inputs)
    provision = inputs.small_lot_provision
    if (
        provision is None
        or inputs.lot_area_sqft is None
        or inputs.lot_area_sqft < provision.trigger_lot_area_sqft
    ):
        return base
    if inputs.lot_width_ft is not None and inputs.lot_width_ft < provision.min_lot_width_ft:
        return base

    if inputs.has_overlay:
        caveat = (
            "An overlay district applies here whose small-lot terms are not modelled; verify the "
            "Title 14 §14-500 series. Showing the base-district result only."
        )
        return replace(base, reasons=[*base.reasons, caveat])

    share = inputs.adjacent_small_share
    threshold = provision.adjacent_small_share
    if share is None or share < threshold:
        note = (
            f"The small-lot provision needs at least {threshold:.0%} of adjacent lots at or below "
            f"{provision.adjacent_small_max_area_sqft:,.0f} sq ft"
            + (f"; here it is {share:.0%}." if share is not None else "; adjacency is unknown.")
        )
        return replace(base, reasons=[*base.reasons, note])

    small_lot_max = int(inputs.lot_area_sqft // provision.min_child_lot_area_sqft)
    if small_lot_max <= (base.max_lots or 0):
        return base

    reason = (
        f"Small-lot provision applies: up to {small_lot_max} lots at the "
        f"{provision.min_child_lot_area_sqft:,.0f} sq ft floor ({provision.citation}), since "
        f"{share:.0%} of adjacent lots are {provision.adjacent_small_max_area_sqft:,.0f} sq ft or "
        "smaller. Subdivision is subject to plan approval and access."
    )
    return replace(
        base,
        can_subdivide=True,
        max_lots=small_lot_max,
        limiting_factor="area",
        is_conforming=True,
        needs_consolidation=False,
        min_lot_area_sqft=provision.min_child_lot_area_sqft,
        reasons=[reason],
    )
