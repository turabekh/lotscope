from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assemblage.service import compute_assemblage
from lotscope.subdivision.analysis import (
    SubdivisionInputs,
    analyze_subdivision,
    small_lot_provision_for,
)
from lotscope.subdivision.schemas import SubdivisionResult
from lotscope.zoning.service import get_parcel_standard, get_unmodelled_overlays

_ADJACENT_BOUNDARY_MIN_FT = 1.0

_PARCEL_SQL = text(
    "SELECT lot_area_sqft, frontage_ft FROM parcel WHERE parcel_number = :parcel_number"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _plausible_width(frontage_ft: float | None, lot_area_sqft: float | None) -> float | None:
    if frontage_ft is None:
        return None
    if lot_area_sqft is not None and frontage_ft >= lot_area_sqft:
        return None
    return frontage_ft


async def _adjacent_small_share(
    session: AsyncSession, parcel_number: str, max_area_sqft: float
) -> float | None:
    assemblage = await compute_assemblage(session, parcel_number)
    if assemblage is None:
        return None
    adjacent = [
        neighbor
        for neighbor in assemblage.neighbors
        if (neighbor.shared_boundary_ft or 0.0) >= _ADJACENT_BOUNDARY_MIN_FT
        and neighbor.lot_area_sqft is not None
    ]
    if not adjacent:
        return None
    small = sum(1 for neighbor in adjacent if (neighbor.lot_area_sqft or 0.0) <= max_area_sqft)
    return small / len(adjacent)


async def analyze_parcel_subdivision(
    session: AsyncSession, parcel_number: str
) -> SubdivisionResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None

    standard = await get_parcel_standard(session, parcel_number)
    lot_area_sqft = _as_float(parcel.lot_area_sqft)
    district_code = standard.code if standard is not None else None
    provision = small_lot_provision_for(district_code)

    adjacent_small_share: float | None = None
    has_overlay = False
    if (
        provision is not None
        and lot_area_sqft is not None
        and (lot_area_sqft >= provision.trigger_lot_area_sqft)
    ):
        adjacent_small_share = await _adjacent_small_share(
            session, parcel_number, provision.adjacent_small_max_area_sqft
        )
        has_overlay = bool(
            await get_unmodelled_overlays(session, parcel_number, district_code or "")
        )

    analysis = analyze_subdivision(
        SubdivisionInputs(
            district_code=district_code,
            lot_area_sqft=lot_area_sqft,
            lot_width_ft=_plausible_width(_as_float(parcel.frontage_ft), lot_area_sqft),
            min_lot_area_sqft=standard.min_lot_area_sqft if standard is not None else None,
            min_lot_width_ft=standard.min_lot_width_ft if standard is not None else None,
            small_lot_provision=provision,
            adjacent_small_share=adjacent_small_share,
            has_overlay=has_overlay,
        )
    )
    sources: list[dict[str, Any]] = [{"source": "opa_properties_public"}]
    if standard is not None:
        sources.append(
            {"source": "zoning_standard", "code": standard.code, "version": standard.code_version}
        )
    return SubdivisionResult(
        parcel_number=parcel_number,
        district_code=analysis.district_code,
        can_subdivide=analysis.can_subdivide,
        max_lots=analysis.max_lots,
        limiting_factor=analysis.limiting_factor,
        is_conforming=analysis.is_conforming,
        needs_consolidation=analysis.needs_consolidation,
        lot_area_sqft=analysis.lot_area_sqft,
        lot_width_ft=analysis.lot_width_ft,
        min_lot_area_sqft=analysis.min_lot_area_sqft,
        min_lot_width_ft=analysis.min_lot_width_ft,
        reasons=analysis.reasons,
        sources=sources,
        computed_at=datetime.now(UTC),
    )
