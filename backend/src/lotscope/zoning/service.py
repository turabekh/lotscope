from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.buildability import (
    DistrictStandard,
    ParcelDimensions,
    assess_buildability,
)
from lotscope.zoning.schemas import BuildabilityResult, DistrictResolution

_PARCEL_SQL = text(
    "SELECT lot_area_sqft, frontage_ft, depth_ft, base_zoning_code, "
    "(geom_2272 IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_SPATIAL_DISTRICT_SQL = text(
    "SELECT zd.code FROM parcel p "
    "JOIN zoning_district zd ON ST_Contains(zd.geom_2272, ST_Centroid(p.geom_2272)) "
    "WHERE p.parcel_number = :parcel_number LIMIT 1"
)
_STANDARD_SQL = text(
    "SELECT code, code_version, permitted_uses, min_lot_area_sqft, min_lot_width_ft, "
    "max_height_ft, max_units, max_occupancy_pct, front_setback_ft, rear_setback_ft, "
    "side_setback_ft "
    "FROM zoning_standard WHERE code = :code ORDER BY code_version DESC LIMIT 1"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def resolve_district(
    session: AsyncSession,
    parcel_number: str,
    *,
    base_zoning_code: str | None,
    has_geometry: bool,
) -> DistrictResolution | None:
    if has_geometry:
        code = await session.scalar(_SPATIAL_DISTRICT_SQL, {"parcel_number": parcel_number})
        if code:
            return DistrictResolution(code=code, method="spatial")
    if base_zoning_code:
        return DistrictResolution(code=base_zoning_code, method="opa_attribute")
    return None


async def _get_standard(session: AsyncSession, code: str) -> DistrictStandard | None:
    row = (await session.execute(_STANDARD_SQL, {"code": code})).one_or_none()
    if row is None:
        return None
    return DistrictStandard(
        code=row.code,
        code_version=row.code_version,
        permitted_uses=list(row.permitted_uses or []),
        min_lot_area_sqft=_as_float(row.min_lot_area_sqft),
        min_lot_width_ft=_as_float(row.min_lot_width_ft),
        max_height_ft=_as_float(row.max_height_ft),
        max_units=row.max_units,
        max_occupancy_pct=_as_float(row.max_occupancy_pct),
        front_setback_ft=_as_float(row.front_setback_ft),
        rear_setback_ft=_as_float(row.rear_setback_ft),
        side_setback_ft=_as_float(row.side_setback_ft),
    )


def _unknown_result(parcel_number: str, computed_at: datetime, reason: str) -> BuildabilityResult:
    return BuildabilityResult(
        parcel_number=parcel_number,
        district_code=None,
        district_method=None,
        cited_section=None,
        conforming=None,
        can_build_by_right=False,
        needs_variance=None,
        by_right_units=None,
        max_height_ft=None,
        buildable_area_sqft=None,
        buildability_score=0.0,
        confidence="low",
        reasons=[reason],
        sources=[],
        computed_at=computed_at,
    )


def _no_standard_result(
    parcel_number: str, resolution: DistrictResolution, computed_at: datetime
) -> BuildabilityResult:
    return BuildabilityResult(
        parcel_number=parcel_number,
        district_code=resolution.code,
        district_method=resolution.method,
        cited_section=None,
        conforming=None,
        can_build_by_right=False,
        needs_variance=None,
        by_right_units=None,
        max_height_ft=None,
        buildable_area_sqft=None,
        buildability_score=0.0,
        confidence="low",
        reasons=[f"No Title 14 standards are loaded for district {resolution.code}."],
        sources=[{"source": "zoning_district", "method": resolution.method}],
        computed_at=computed_at,
    )


def _build_result(
    parcel_number: str,
    parcel: Row[Any],
    resolution: DistrictResolution,
    standard: DistrictStandard,
    computed_at: datetime,
) -> BuildabilityResult:
    dims = ParcelDimensions(
        lot_area_sqft=_as_float(parcel.lot_area_sqft),
        lot_width_ft=_as_float(parcel.frontage_ft),
        depth_ft=_as_float(parcel.depth_ft),
    )
    buildability = assess_buildability(dims, standard)
    sources = [
        {"source": "zoning_district", "method": resolution.method},
        {"source": "zoning_standard", "code": standard.code, "version": standard.code_version},
    ]
    return BuildabilityResult(
        parcel_number=parcel_number,
        district_code=buildability.district_code,
        district_method=resolution.method,
        cited_section=buildability.cited_section,
        conforming=buildability.conforming,
        can_build_by_right=buildability.can_build_by_right,
        needs_variance=buildability.needs_variance,
        by_right_units=buildability.by_right_units,
        max_height_ft=buildability.max_height_ft,
        buildable_area_sqft=buildability.buildable_area_sqft,
        buildability_score=buildability.buildability_score,
        confidence=buildability.confidence,
        reasons=buildability.reasons,
        sources=sources,
        computed_at=computed_at,
    )


async def assess_parcel(session: AsyncSession, parcel_number: str) -> BuildabilityResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    computed_at = datetime.now(UTC)
    resolution = await resolve_district(
        session,
        parcel_number,
        base_zoning_code=parcel.base_zoning_code,
        has_geometry=parcel.has_geometry,
    )
    if resolution is None:
        return _unknown_result(
            parcel_number, computed_at, "Zoning district could not be resolved for this parcel."
        )
    standard = await _get_standard(session, resolution.code)
    if standard is None:
        return _no_standard_result(parcel_number, resolution, computed_at)
    return _build_result(parcel_number, parcel, resolution, standard, computed_at)
