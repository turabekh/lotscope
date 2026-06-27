from dataclasses import dataclass, field
from typing import Literal

Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ParcelDimensions:
    lot_area_sqft: float | None = None
    lot_width_ft: float | None = None
    depth_ft: float | None = None


@dataclass(frozen=True)
class DistrictStandard:
    code: str
    code_version: str
    permitted_uses: list[str] = field(default_factory=list)
    min_lot_area_sqft: float | None = None
    min_lot_width_ft: float | None = None
    max_height_ft: float | None = None
    max_units: int | None = None
    max_occupancy_pct: float | None = None
    front_setback_ft: float | None = None
    rear_setback_ft: float | None = None
    side_setback_ft: float | None = None
    requires_master_plan: bool = False


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
) -> float | None:
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
        return area
    if dims.lot_area_sqft and standard.max_occupancy_pct:
        area = round(dims.lot_area_sqft * standard.max_occupancy_pct / 100, 1)
        reasons.append(
            f"Estimated buildable footprint ~{area:.0f} sqft at "
            f"{standard.max_occupancy_pct:.0f}% lot coverage."
        )
        return area
    return None


def _confidence(dims: ParcelDimensions) -> Confidence:
    known = [dims.lot_area_sqft is not None, dims.lot_width_ft is not None]
    if all(known):
        return "high"
    if any(known):
        return "medium"
    return "low"


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


def assess_buildability(dims: ParcelDimensions, standard: DistrictStandard) -> Buildability:
    reasons: list[str] = []
    conforming = _check_conformance(dims, standard, reasons)
    buildable_area = _net_buildable_area(dims, standard, reasons)

    has_permitted_uses = bool(standard.permitted_uses)
    if not has_permitted_uses:
        reasons.append(
            f"No by-right uses are recorded for {standard.code}; confirm permitted uses "
            "in Title 14 before relying on this."
        )

    needs_variance = (not conforming) if conforming is not None else None
    if needs_variance:
        reasons.append(
            "Lot is non-conforming on minimum dimensions; new construction will likely "
            "need a variance or special exception."
        )

    if standard.requires_master_plan:
        reasons.append(
            f"District {standard.code} is a special-purpose district; development is not "
            "permitted by-right and requires an approved master plan or equivalent review."
        )
        can_build_by_right = False
        by_right_units = None
    else:
        can_build_by_right = conforming is True and has_permitted_uses
        by_right_units = standard.max_units
        if standard.max_units is not None:
            reasons.append(
                f"District {standard.code} permits up to {standard.max_units} unit(s) by-right."
            )

    return Buildability(
        district_code=standard.code,
        cited_section=f"{standard.code} (Title 14, {standard.code_version})",
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
        confidence=_confidence(dims),
        reasons=reasons,
        requires_master_plan=standard.requires_master_plan,
    )
