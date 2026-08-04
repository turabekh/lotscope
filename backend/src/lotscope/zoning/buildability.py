from dataclasses import dataclass, field
from typing import Any, Literal

from lotscope.zoning.confidence import (
    Confidence,
    CriticalUnknown,
    dimensional_confidence,
    resolve_confidence,
)
from lotscope.zoning.dispositions import is_unregulated

UnitBasis = Literal["per_unit", "far_estimate", "flat_cap"]
FootprintBasis = Literal["setback_calculated", "coverage_estimate", "unavailable"]

_AVG_GROSS_FLOOR_PER_UNIT_SQFT = 1100.0


@dataclass(frozen=True)
class ParcelDimensions:
    lot_area_sqft: float | None = None
    lot_width_ft: float | None = None
    depth_ft: float | None = None


@dataclass(frozen=True)
class DistrictStandard:
    code: str
    code_version: str
    citation_label: str = "Title 14"
    permitted_uses: list[str] = field(default_factory=list)
    min_lot_area_sqft: float | None = None
    min_lot_width_ft: float | None = None
    max_height_ft: float | None = None
    max_units: int | None = None
    lot_area_per_unit_sqft: float | None = None
    max_floor_area_ratio_pct: float | None = None
    max_occupancy_pct: float | None = None
    front_setback_ft: float | None = None
    rear_setback_ft: float | None = None
    side_setback_ft: float | None = None
    requires_master_plan: bool = False
    field_dispositions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Buildability:
    district_code: str
    cited_section: str
    conforming: bool | None
    can_build_by_right: bool
    needs_variance: bool | None
    by_right_units: int | None
    max_height_ft: float | None
    buildable_area_sqft: float | None
    buildability_score: float
    confidence: Confidence
    reasons: list[str]
    critical_unknowns: tuple[CriticalUnknown, ...] = ()
    requires_master_plan: bool = False


def _check_conformance(
    dims: ParcelDimensions, standard: DistrictStandard, reasons: list[str]
) -> bool | None:
    if standard.min_lot_area_sqft is None and standard.min_lot_width_ft is None:
        return True

    unknown = False
    conforming = True

    if standard.min_lot_area_sqft is not None:
        if dims.lot_area_sqft is None:
            unknown = True
        elif dims.lot_area_sqft < standard.min_lot_area_sqft:
            conforming = False
            reasons.append(
                f"Lot area {dims.lot_area_sqft:.0f} sqft is below the "
                f"{standard.min_lot_area_sqft:.0f} sqft minimum for {standard.code}."
            )

    if standard.min_lot_width_ft is not None:
        if dims.lot_width_ft is None:
            unknown = True
        elif dims.lot_width_ft < standard.min_lot_width_ft:
            conforming = False
            reasons.append(
                f"Lot width {dims.lot_width_ft:.0f} ft is below the "
                f"{standard.min_lot_width_ft:.0f} ft minimum for {standard.code}."
            )

    if not conforming:
        return False
    if unknown:
        reasons.append(
            "Lot dimensions are incomplete; conformance with district minimums "
            "could not be fully verified."
        )
        return None
    reasons.append(f"Lot meets the dimensional minimums for {standard.code}.")
    return True


def _net_buildable_area(
    dims: ParcelDimensions, standard: DistrictStandard, reasons: list[str]
) -> tuple[float | None, FootprintBasis]:
    has_setbacks = (
        standard.front_setback_ft is not None
        or standard.rear_setback_ft is not None
        or standard.side_setback_ft is not None
    )
    if dims.lot_width_ft and dims.depth_ft and has_setbacks:
        side = standard.side_setback_ft or 0.0
        front = standard.front_setback_ft or 0.0
        rear = standard.rear_setback_ft or 0.0
        net_width = max(0.0, dims.lot_width_ft - 2 * side)
        net_depth = max(0.0, dims.depth_ft - front - rear)
        area = round(net_width * net_depth, 1)
        reasons.append(f"Estimated buildable footprint ~{area:.0f} sqft after setbacks.")
        return area, "setback_calculated"
    if dims.lot_area_sqft and standard.max_occupancy_pct:
        area = round(dims.lot_area_sqft * standard.max_occupancy_pct / 100, 1)
        reasons.append(
            f"Estimated buildable footprint ~{area:.0f} sqft at "
            f"{standard.max_occupancy_pct:.0f}% lot coverage."
        )
        return area, "coverage_estimate"
    return None, "unavailable"


def _critical_unknowns(
    dims: ParcelDimensions,
    standard: DistrictStandard,
    conforming: bool | None,
    footprint_basis: FootprintBasis,
    has_permitted_uses: bool,
) -> tuple[CriticalUnknown, ...]:
    unknowns: list[CriticalUnknown] = []
    if dims.lot_area_sqft is None or dims.lot_width_ft is None:
        unknowns.append("dimensions_incomplete")
    if conforming is None:
        unknowns.append("conformance_unresolved")
    if footprint_basis != "setback_calculated":
        unknowns.append("footprint_not_setback_derived")
    if standard.max_height_ft is None and not is_unregulated(
        standard.field_dispositions, "max_height_ft"
    ):
        unknowns.append("height_standard_missing")
    if not has_permitted_uses:
        unknowns.append("permitted_uses_missing")
    return tuple(unknowns)


def _score(
    conforming: bool | None,
    has_permitted_uses: bool,
    buildable_area: float | None,
    by_right_units: int | None,
    requires_master_plan: bool,
) -> float:
    if requires_master_plan:
        return 25.0 if has_permitted_uses else 10.0
    score = 0.0
    if conforming is True:
        score += 50.0
    elif conforming is None:
        score += 20.0
    if has_permitted_uses:
        score += 20.0
    if buildable_area is not None and buildable_area > 0:
        score += 20.0
    if by_right_units:
        score += 10.0
    return min(100.0, score)


def by_right_unit_count(standard: DistrictStandard, lot_area_sqft: float | None) -> int | None:
    if (
        "multi_family" in standard.permitted_uses
        and standard.lot_area_per_unit_sqft
        and lot_area_sqft is not None
    ):
        return max(1, int(lot_area_sqft // standard.lot_area_per_unit_sqft))
    return standard.max_units


def far_unit_estimate(standard: DistrictStandard, lot_area_sqft: float | None) -> int | None:
    if (
        "multi_family" in standard.permitted_uses
        and not standard.requires_master_plan
        and standard.max_floor_area_ratio_pct
        and lot_area_sqft is not None
    ):
        floor_area = lot_area_sqft * standard.max_floor_area_ratio_pct / 100.0
        return max(1, int(floor_area / _AVG_GROSS_FLOOR_PER_UNIT_SQFT))
    return None


def estimate_density_units(
    standard: DistrictStandard, lot_area_sqft: float | None
) -> tuple[int | None, UnitBasis | None]:
    if (
        "multi_family" in standard.permitted_uses
        and standard.lot_area_per_unit_sqft
        and lot_area_sqft is not None
    ):
        return max(1, int(lot_area_sqft // standard.lot_area_per_unit_sqft)), "per_unit"
    far = far_unit_estimate(standard, lot_area_sqft)
    if far is not None:
        return far, "far_estimate"
    if standard.max_units is not None:
        return standard.max_units, "flat_cap"
    return None, None


def assess_buildability(dims: ParcelDimensions, standard: DistrictStandard) -> Buildability:
    reasons: list[str] = []
    conforming = _check_conformance(dims, standard, reasons)
    buildable_area, footprint_basis = _net_buildable_area(dims, standard, reasons)

    has_permitted_uses = bool(standard.permitted_uses)
    if not has_permitted_uses:
        reasons.append(
            f"No by-right uses are recorded for {standard.code}; confirm permitted uses "
            f"in {standard.citation_label} before relying on this."
        )

    needs_variance = (not conforming) if conforming is not None else None
    if needs_variance:
        reasons.append(
            "Lot is non-conforming on minimum dimensions; new construction will likely "
            "need a variance or special exception."
        )

    if standard.requires_master_plan:
        reasons.append(
            f"District {standard.code} does not permit development by-right; an approved master "
            "plan or equivalent review is required before any construction."
        )
        can_build_by_right = False
        by_right_units = None
    else:
        can_build_by_right = conforming is True and has_permitted_uses
        by_right_units = by_right_unit_count(standard, dims.lot_area_sqft)
        if standard.lot_area_per_unit_sqft is not None and by_right_units is not None:
            reasons.append(
                f"District {standard.code} permits about {by_right_units} unit(s) by-right at "
                f"~{standard.lot_area_per_unit_sqft:.0f} sqft of lot area per unit; the count "
                "scales with lot size."
            )
        elif by_right_units is not None:
            reasons.append(
                f"District {standard.code} permits up to {by_right_units} unit(s) by-right."
            )

    critical_unknowns = _critical_unknowns(
        dims, standard, conforming, footprint_basis, has_permitted_uses
    )
    return Buildability(
        district_code=standard.code,
        cited_section=f"{standard.code} ({standard.citation_label}, {standard.code_version})",
        conforming=conforming,
        can_build_by_right=can_build_by_right,
        needs_variance=needs_variance,
        by_right_units=by_right_units,
        max_height_ft=standard.max_height_ft,
        buildable_area_sqft=buildable_area,
        buildability_score=_score(
            conforming,
            has_permitted_uses,
            buildable_area,
            by_right_units,
            standard.requires_master_plan,
        ),
        confidence=resolve_confidence(
            dimensional_confidence(
                lot_area_known=dims.lot_area_sqft is not None,
                lot_width_known=dims.lot_width_ft is not None,
            ),
            critical_unknowns,
        ),
        reasons=reasons,
        critical_unknowns=critical_unknowns,
        requires_master_plan=standard.requires_master_plan,
    )
