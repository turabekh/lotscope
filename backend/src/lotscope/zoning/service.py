import json
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.markets.capabilities import zoning_citation_label
from lotscope.zoning.buildability import (
    DistrictStandard,
    ParcelDimensions,
    UnitBasis,
    assess_buildability,
    estimate_density_units,
)
from lotscope.zoning.codes import normalize_zoning_code
from lotscope.zoning.confidence import (
    CriticalUnknown,
    critical_unknown_reasons,
    dimensional_confidence,
    resolve_confidence,
)
from lotscope.zoning.envelope import estimate_floors, representative_inset_ft
from lotscope.zoning.schemas import BuildabilityResult, DistrictResolution, EnvelopeResult

_PARCEL_SQL = text(
    "SELECT lot_area_sqft, frontage_ft, depth_ft, base_zoning_code, "
    "(geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_SPATIAL_DISTRICT_SQL = text(
    "SELECT zd.code FROM parcel p "
    "JOIN zoning_district zd ON zd.market_code = p.market_code "
    "AND ST_Contains(zd.geom_local, ST_Centroid(p.geom_local)) "
    "WHERE p.parcel_number = :parcel_number "
    "ORDER BY ST_Area(ST_Intersection("
    "ST_MakeValid(zd.geom_local), ST_MakeValid(p.geom_local))) DESC, zd.code ASC "
    "LIMIT 1"
)
_PARCEL_OVERLAYS_SQL = text(
    "SELECT array_agg(DISTINCT zo.name ORDER BY zo.name) AS names FROM parcel p "
    "JOIN zoning_overlay zo ON zo.market_code = p.market_code "
    "AND ST_Intersects(zo.geom_local, p.geom_local) "
    "WHERE p.parcel_number = :parcel_number AND p.geom_local IS NOT NULL AND zo.name IS NOT NULL"
)


async def get_parcel_overlays(session: AsyncSession, parcel_number: str) -> list[str]:
    names = await session.scalar(_PARCEL_OVERLAYS_SQL, {"parcel_number": parcel_number})
    return list(names or [])


_FOOTPRINT_SQL = text(
    "SELECT ST_AsGeoJSON(ST_Transform(geom_local, 4326), 6) AS lot_geojson, "
    "ST_AsGeoJSON(ST_Transform(ST_Buffer(geom_local, -CAST(:inset AS double precision)), 4326), 6) "
    "AS buildable_geojson, "
    "ST_Area(ST_Buffer(geom_local, -CAST(:inset AS double precision))) AS buildable_area, "
    "ST_Area(geom_local) AS lot_area "
    "FROM parcel WHERE parcel_number = :parcel_number AND geom_local IS NOT NULL"
)
_MIN_BUILDABLE_RATIO = 0.05
_STANDARD_SQL = text(
    "SELECT code, code_version, permitted_uses, min_lot_area_sqft, min_lot_width_ft, "
    "max_height_ft, max_units, lot_area_per_unit_sqft, max_floor_area_ratio_pct, "
    "max_occupancy_pct, front_setback_ft, rear_setback_ft, side_setback_ft, requires_master_plan, "
    "field_dispositions "
    "FROM zoning_standard WHERE upper(replace(replace(code, '-', ''), ' ', '')) = :code "
    "AND market_code = :market_code "
    "ORDER BY code_version DESC LIMIT 1"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _market_of(parcel_number: str) -> str:
    return parcel_number.split(":", 1)[0] if ":" in parcel_number else "phl"


async def resolve_district(
    session: AsyncSession,
    parcel_number: str,
    *,
    base_zoning_code: str | None,
    has_geometry: bool,
) -> DistrictResolution | None:
    spatial_code = (
        await session.scalar(_SPATIAL_DISTRICT_SQL, {"parcel_number": parcel_number})
        if has_geometry
        else None
    )
    if spatial_code:
        corroborated = base_zoning_code is not None and normalize_zoning_code(
            base_zoning_code
        ) == normalize_zoning_code(spatial_code)
        return DistrictResolution(code=spatial_code, method="spatial", corroborated=corroborated)
    if base_zoning_code:
        return DistrictResolution(code=base_zoning_code, method="opa_attribute")
    return None


_REFRESH_RESOLVED_DISTRICT_SQL = text(
    "UPDATE parcel p SET resolved_zoning_code = sub.code, "
    "resolved_zoning_source = 'spatial', updated_at = now() "
    "FROM ("
    "  SELECT DISTINCT ON (p2.parcel_number) p2.parcel_number, zd.code "
    "  FROM parcel p2 "
    "  JOIN zoning_district zd ON zd.market_code = p2.market_code "
    "    AND ST_Contains(zd.geom_local, ST_Centroid(p2.geom_local)) "
    "  WHERE p2.market_code = :market_code "
    "    AND (p2.base_zoning_code IS NULL OR p2.base_zoning_code = '') "
    "    AND p2.geom_local IS NOT NULL "
    "  ORDER BY p2.parcel_number, "
    "    ST_Area(ST_Intersection(ST_MakeValid(zd.geom_local), ST_MakeValid(p2.geom_local))) DESC, "
    "    zd.code ASC"
    ") sub "
    "WHERE p.parcel_number = sub.parcel_number "
    "AND p.resolved_zoning_code IS DISTINCT FROM sub.code"
)


async def refresh_resolved_districts(session: AsyncSession, market_code: str) -> int:
    result = cast(
        "CursorResult[Any]",
        await session.execute(_REFRESH_RESOLVED_DISTRICT_SQL, {"market_code": market_code}),
    )
    return result.rowcount or 0


async def _get_standard(
    session: AsyncSession, code: str, market_code: str
) -> DistrictStandard | None:
    row = (
        await session.execute(
            _STANDARD_SQL, {"code": normalize_zoning_code(code), "market_code": market_code}
        )
    ).one_or_none()
    if row is None:
        return None
    return DistrictStandard(
        code=row.code,
        code_version=row.code_version,
        citation_label=zoning_citation_label(market_code),
        permitted_uses=list(row.permitted_uses or []),
        min_lot_area_sqft=_as_float(row.min_lot_area_sqft),
        min_lot_width_ft=_as_float(row.min_lot_width_ft),
        max_height_ft=_as_float(row.max_height_ft),
        max_units=row.max_units,
        lot_area_per_unit_sqft=_as_float(row.lot_area_per_unit_sqft),
        max_floor_area_ratio_pct=_as_float(row.max_floor_area_ratio_pct),
        max_occupancy_pct=_as_float(row.max_occupancy_pct),
        front_setback_ft=_as_float(row.front_setback_ft),
        rear_setback_ft=_as_float(row.rear_setback_ft),
        side_setback_ft=_as_float(row.side_setback_ft),
        requires_master_plan=row.requires_master_plan,
        field_dispositions=dict(row.field_dispositions or {}),
    )


async def is_known_district(session: AsyncSession, code: str, market_code: str) -> bool:
    return await _get_standard(session, code, market_code) is not None


async def get_parcel_standard(session: AsyncSession, parcel_number: str) -> DistrictStandard | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    resolution = await resolve_district(
        session,
        parcel_number,
        base_zoning_code=parcel.base_zoning_code,
        has_geometry=parcel.has_geometry,
    )
    if resolution is None:
        return None
    return await _get_standard(session, resolution.code, _market_of(parcel_number))


async def assemblage_unit_estimate(
    session: AsyncSession,
    parcel_number: str,
    *,
    current_area_sqft: float | None,
    combined_area_sqft: float | None,
) -> tuple[int | None, int | None, UnitBasis | None]:
    standard = await get_parcel_standard(session, parcel_number)
    if standard is None:
        return None, None, None
    current_units, basis = estimate_density_units(standard, current_area_sqft)
    combined_units, combined_basis = estimate_density_units(standard, combined_area_sqft)
    return current_units, combined_units, basis or combined_basis


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
        reasons=[
            f"No {zoning_citation_label(_market_of(parcel_number))} standards are loaded "
            f"for district {resolution.code}."
        ],
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
    critical_unknowns: list[CriticalUnknown] = list(buildability.critical_unknowns)
    if not resolution.corroborated:
        critical_unknowns.append("district_uncorroborated")
    if "provisional" in standard.code_version:
        critical_unknowns.append("standards_provisional")
    confidence = resolve_confidence(
        dimensional_confidence(
            lot_area_known=dims.lot_area_sqft is not None,
            lot_width_known=dims.lot_width_ft is not None,
        ),
        critical_unknowns,
    )
    reasons = list(buildability.reasons) + critical_unknown_reasons(critical_unknowns)
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
        confidence=confidence,
        critical_unknowns=critical_unknowns,
        requires_master_plan=buildability.requires_master_plan,
        reasons=reasons,
        sources=sources,
        computed_at=computed_at,
    )


def _envelope_unavailable(
    parcel_number: str,
    computed_at: datetime,
    district_code: str | None,
    cited_section: str | None,
    reason: str,
    *,
    lot_footprint: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> EnvelopeResult:
    return EnvelopeResult(
        parcel_number=parcel_number,
        available=False,
        district_code=district_code,
        cited_section=cited_section,
        max_height_ft=None,
        estimated_floors=None,
        applied_setback_ft=None,
        buildable_area_sqft=None,
        lot_footprint=lot_footprint,
        buildable_footprint=lot_footprint,
        reasons=[reason],
        sources=sources or [],
        computed_at=computed_at,
    )


async def compute_envelope(session: AsyncSession, parcel_number: str) -> EnvelopeResult | None:
    parcel = (await session.execute(_PARCEL_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    computed_at = datetime.now(UTC)
    if not parcel.has_geometry:
        return _envelope_unavailable(
            parcel_number,
            computed_at,
            None,
            None,
            "No footprint geometry is available for this parcel.",
        )

    resolution = await resolve_district(
        session,
        parcel_number,
        base_zoning_code=parcel.base_zoning_code,
        has_geometry=parcel.has_geometry,
    )
    standard = (
        await _get_standard(session, resolution.code, _market_of(parcel_number))
        if resolution is not None
        else None
    )
    inset = (
        representative_inset_ft(
            standard.front_setback_ft, standard.side_setback_ft, standard.rear_setback_ft
        )
        if standard is not None
        else 0.0
    )

    row = (
        await session.execute(_FOOTPRINT_SQL, {"parcel_number": parcel_number, "inset": inset})
    ).one_or_none()
    if row is None or row.lot_geojson is None:
        return _envelope_unavailable(
            parcel_number,
            computed_at,
            resolution.code if resolution else None,
            None,
            "No footprint geometry is available for this parcel.",
        )

    lot_footprint = json.loads(row.lot_geojson)
    lot_area = _as_float(row.lot_area)
    buildable_area = _as_float(row.buildable_area)
    reasons: list[str] = []

    too_small = (
        inset > 0
        and lot_area is not None
        and (buildable_area is None or buildable_area < _MIN_BUILDABLE_RATIO * lot_area)
    )
    if too_small:
        buildable_footprint = lot_footprint
        applied_setback = 0.0
        buildable_area = lot_area
        reasons.append("Lot is too small to apply setbacks cleanly; showing the full footprint.")
    else:
        buildable_footprint = (
            json.loads(row.buildable_geojson) if row.buildable_geojson else lot_footprint
        )
        applied_setback = inset

    sources: list[dict[str, Any]] = [{"source": "pwd_parcel", "field": "geom_local"}]
    if resolution is not None:
        sources.append({"source": "zoning_district", "method": resolution.method})

    if standard is None:
        district_code = resolution.code if resolution else None
        reason = (
            f"No {zoning_citation_label(_market_of(parcel_number))} standards are loaded "
            f"for district {district_code}."
            if district_code
            else "Zoning district could not be resolved for this parcel."
        )
        result = _envelope_unavailable(
            parcel_number,
            computed_at,
            district_code,
            None,
            reason,
            lot_footprint=lot_footprint,
            sources=sources,
        )
        return result

    sources.append(
        {"source": "zoning_standard", "code": standard.code, "version": standard.code_version}
    )
    cited_section = f"{standard.code} ({standard.citation_label}, {standard.code_version})"
    if standard.max_height_ft is None:
        reasons.append(f"No by-right height standard is recorded for district {standard.code}.")
    if applied_setback > 0:
        front = standard.front_setback_ft or 0
        side = standard.side_setback_ft or 0
        rear = standard.rear_setback_ft or 0
        reasons.append(
            f"Footprint inset by an average setback of {applied_setback:.1f} ft "
            f"(front {front:.0f}, side {side:.0f}, rear {rear:.0f}). "
            "Approximate massing for guidance only."
        )

    floors = estimate_floors(standard.max_height_ft)
    return EnvelopeResult(
        parcel_number=parcel_number,
        available=standard.max_height_ft is not None,
        district_code=standard.code,
        cited_section=cited_section,
        max_height_ft=standard.max_height_ft,
        estimated_floors=floors,
        applied_setback_ft=applied_setback,
        buildable_area_sqft=round(buildable_area, 1) if buildable_area is not None else None,
        lot_footprint=lot_footprint,
        buildable_footprint=buildable_footprint,
        reasons=reasons,
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
    standard = await _get_standard(session, resolution.code, _market_of(parcel_number))
    if standard is None:
        return _no_standard_result(parcel_number, resolution, computed_at)
    return _build_result(parcel_number, parcel, resolution, standard, computed_at)
