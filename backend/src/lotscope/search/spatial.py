import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ValidationError
from lotscope.core.markets import market_code
from lotscope.search.schemas import AreaSearchRequest, SpatialParcelResult

MAX_RADIUS_M = 5000.0
_POLYGON_TYPES = frozenset({"Polygon", "MultiPolygon"})

_SELECT = (
    "p.parcel_number, p.address, p.owner, p.base_zoning_code, p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score, "
    "ST_X(ST_PointOnSurface(p.geom_4326)) AS lng, "
    "ST_Y(ST_PointOnSurface(p.geom_4326)) AS lat"
)
_JOINS = (
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "LEFT JOIN parcel_distress pd ON pd.parcel_number = p.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number"
)
_POINT = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography"


def build_filters(
    *,
    market: str = "phl",
    vacant_only: bool,
    zoning_codes: list[str],
    min_lot_area_sqft: float | None = None,
    max_lot_area_sqft: float | None = None,
    min_market_value: float | None = None,
    max_market_value: float | None = None,
    min_opportunity_score: int | None = None,
    min_distress_score: int | None = None,
    delinquent_only: bool = False,
    sheriff_sale_only: bool = False,
    underpriced_only: bool = False,
    by_right_only: bool = False,
) -> tuple[str, dict[str, Any]]:
    conditions = ["p.geom_4326 IS NOT NULL", "p.market_code = :market"]
    params: dict[str, Any] = {"market": market}
    if vacant_only:
        conditions.append("coalesce(p.is_vacant, false) = true")
    if zoning_codes:
        conditions.append("p.base_zoning_code = ANY(:zoning_codes)")
        params["zoning_codes"] = [code.strip().upper() for code in zoning_codes if code.strip()]
    if min_lot_area_sqft is not None:
        conditions.append("p.lot_area_sqft >= :min_lot_area")
        params["min_lot_area"] = min_lot_area_sqft
    if max_lot_area_sqft is not None:
        conditions.append("p.lot_area_sqft <= :max_lot_area")
        params["max_lot_area"] = max_lot_area_sqft
    if min_market_value is not None:
        conditions.append("p.market_value >= :min_value")
        params["min_value"] = min_market_value
    if max_market_value is not None:
        conditions.append("p.market_value <= :max_value")
        params["max_value"] = max_market_value
    if min_opportunity_score is not None:
        conditions.append("pv.opportunity_score >= :min_score")
        params["min_score"] = min_opportunity_score
    if min_distress_score is not None:
        conditions.append("pd.score >= :min_distress")
        params["min_distress"] = min_distress_score
    if delinquent_only:
        conditions.append("coalesce(ts.is_delinquent, false) = true")
    if sheriff_sale_only:
        conditions.append("coalesce(ts.in_sheriff_sale, false) = true")
    if underpriced_only:
        conditions.append("coalesce(pv.is_underpriced, false) = true")
    if by_right_only:
        conditions.append("coalesce(pv.can_build_by_right, false) = true")
    return " AND ".join(conditions), params


def _filters_for(request: AreaSearchRequest) -> tuple[str, dict[str, Any]]:
    return build_filters(
        market=market_code(request.market),
        vacant_only=request.vacant_only,
        zoning_codes=request.zoning_codes,
        min_lot_area_sqft=request.min_lot_area_sqft,
        max_lot_area_sqft=request.max_lot_area_sqft,
        min_market_value=request.min_market_value,
        max_market_value=request.max_market_value,
        min_opportunity_score=request.min_opportunity_score,
        min_distress_score=request.min_distress_score,
        delinquent_only=request.delinquent_only,
        sheriff_sale_only=request.sheriff_sale_only,
        underpriced_only=request.underpriced_only,
        by_right_only=request.by_right_only,
    )


def _result(row: Row[Any], *, with_distance: bool) -> SpatialParcelResult:
    return SpatialParcelResult(
        parcel_number=row.parcel_number,
        address=row.address,
        owner=row.owner,
        base_zoning_code=row.base_zoning_code,
        is_vacant=row.is_vacant,
        market_value=float(row.market_value) if row.market_value is not None else None,
        opportunity_score=row.opportunity_score,
        lng=float(row.lng) if row.lng is not None else None,
        lat=float(row.lat) if row.lat is not None else None,
        distance_m=round(float(row.distance_m), 1) if with_distance else None,
    )


async def _count(session: AsyncSession, where: str, spatial: str, params: dict[str, Any]) -> int:
    total = (
        await session.execute(
            text(f"SELECT count(*) FROM parcel p {_JOINS} WHERE {where} AND {spatial}"), params
        )
    ).scalar_one()
    return int(total)


async def _search_radius(
    session: AsyncSession, request: AreaSearchRequest
) -> tuple[list[SpatialParcelResult], int]:
    assert request.center is not None
    assert request.radius_m is not None
    radius = min(request.radius_m, MAX_RADIUS_M)
    where, params = _filters_for(request)
    params = {**params, "lng": request.center.lng, "lat": request.center.lat, "radius_m": radius}
    spatial = f"ST_DWithin(p.geom_4326::geography, {_POINT}, :radius_m)"
    rows = (
        await session.execute(
            text(
                f"SELECT {_SELECT}, "
                f"ST_Distance(p.geom_4326::geography, {_POINT}) AS distance_m "
                f"FROM parcel p {_JOINS} "
                f"WHERE {where} AND {spatial} "
                "ORDER BY distance_m LIMIT :limit"
            ),
            {**params, "limit": request.limit},
        )
    ).all()
    total = await _count(session, where, spatial, params)
    return [_result(row, with_distance=True) for row in rows], total


async def _search_polygon(
    session: AsyncSession, request: AreaSearchRequest
) -> tuple[list[SpatialParcelResult], int]:
    polygon = request.polygon
    assert polygon is not None
    if polygon.get("type") not in _POLYGON_TYPES:
        raise ValidationError("polygon must be a GeoJSON Polygon or MultiPolygon geometry.")
    where, params = _filters_for(request)
    params = {**params, "polygon": json.dumps(polygon)}
    spatial = "ST_Intersects(p.geom_4326, ST_SetSRID(ST_GeomFromGeoJSON(:polygon), 4326))"
    rows = (
        await session.execute(
            text(
                f"SELECT {_SELECT} "
                f"FROM parcel p {_JOINS} "
                f"WHERE {where} AND {spatial} "
                "ORDER BY pv.opportunity_score DESC NULLS LAST, p.parcel_number LIMIT :limit"
            ),
            {**params, "limit": request.limit},
        )
    ).all()
    total = await _count(session, where, spatial, params)
    return [_result(row, with_distance=False) for row in rows], total


async def _search_neighborhood(
    session: AsyncSession, request: AreaSearchRequest
) -> tuple[list[SpatialParcelResult], int]:
    assert request.neighborhood is not None
    where, params = _filters_for(request)
    params = {**params, "neighborhood": request.neighborhood}
    spatial = (
        "ST_Intersects(p.geom_4326, "
        "(SELECT ST_Union(n.geom_4326) FROM neighborhood n WHERE n.name = :neighborhood))"
    )
    rows = (
        await session.execute(
            text(
                f"SELECT {_SELECT} "
                f"FROM parcel p {_JOINS} "
                f"WHERE {where} AND {spatial} "
                "ORDER BY pv.opportunity_score DESC NULLS LAST, p.parcel_number LIMIT :limit"
            ),
            {**params, "limit": request.limit},
        )
    ).all()
    total = await _count(session, where, spatial, params)
    return [_result(row, with_distance=False) for row in rows], total


async def search_area(
    session: AsyncSession, request: AreaSearchRequest
) -> tuple[list[SpatialParcelResult], int]:
    if request.polygon is not None:
        return await _search_polygon(session, request)
    if request.neighborhood is not None:
        return await _search_neighborhood(session, request)
    return await _search_radius(session, request)
