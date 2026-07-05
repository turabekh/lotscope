import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assemblage.service import compute_assemblage
from lotscope.risk.service import _has_street_frontage
from lotscope.search.schemas import AreaSearchRequest, GeoPoint
from lotscope.search.spatial import search_area
from lotscope.valuation.service import value_parcel
from lotscope.verdict.service import compute_verdict
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration

_SUBJECT = "POLYGON((0 0,0 10,10 10,10 0,0 0))"
_NEAR = "POLYGON((50 0,50 10,60 10,60 0,50 0))"
_TOUCHING = "POLYGON((10 0,10 10,20 10,20 0,10 0))"
_COVER = "POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))"
_STREET = "LINESTRING(0 12,10 12)"


async def _market(session: AsyncSession, code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO market (code, name, state, url_slug, local_srid, map_center, "
            "default_zoom, timezone, deal_assumption_overrides, launch_status) VALUES "
            "(:c, :c, 'XX', :c, 2272, '[0,0]'::jsonb, 12, 'UTC', '{}'::jsonb, 'live')"
        ),
        {"c": code},
    )


async def _parcel(
    session: AsyncSession, pn: str, market: str, poly: str, *, zoning: str | None = None
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, is_vacant, base_zoning_code, "
            "lot_area_sqft, frontage_ft, geom_local, geom_4326) VALUES "
            "(:pn, :m, TRUE, :z, 2000, 20, ST_GeomFromText(:poly, 2272), "
            "ST_Transform(ST_GeomFromText(:poly, 2272), 4326))"
        ),
        {"pn": pn, "m": market, "z": zoning, "poly": poly},
    )


async def _sale(session: AsyncSession, pn: str, doc: str) -> None:
    await session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, sale_price, sale_date) "
            "VALUES (:pn, :doc, 200000, '2025-06-01')"
        ),
        {"pn": pn, "doc": doc},
    )


async def _district(session: AsyncSession, market: str, code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_district (code, market_code, geom_local) "
            "VALUES (:code, :m, ST_GeomFromText(:poly, 2272))"
        ),
        {"code": code, "m": market, "poly": _COVER},
    )


async def _street(session: AsyncSession, market: str) -> None:
    await session.execute(
        text(
            "INSERT INTO street_centerline (market_code, geom_local) "
            "VALUES (:m, ST_GeomFromText(:poly, 2272))"
        ),
        {"m": market, "poly": _STREET},
    )


async def _plant_two_markets(session: AsyncSession) -> None:
    await _market(session, "zzz")
    await seed_zoning_standards(session)
    # subject in zzz
    await _parcel(session, "zzz:S", "zzz", _SUBJECT, zoning="RSA-5")
    # a zzz comp + a phl decoy at the SAME nearby location
    await _parcel(session, "zzz:C", "zzz", _NEAR, zoning="RSA-5")
    await _sale(session, "zzz:C", "DOC-ZZZ")
    await _parcel(session, "phl:C", "phl", _NEAR, zoning="RSA-5")
    await _sale(session, "phl:C", "DOC-PHL")
    # a zzz neighbor + a phl decoy both touching the subject
    await _parcel(session, "zzz:N", "zzz", _TOUCHING)
    await _parcel(session, "phl:N", "phl", _TOUCHING)
    # only a phl street sits by the subject; zzz has none
    await _street(session, "phl")
    # zzz district RSA-5 and a phl district CMX-3 both cover the subject
    await _district(session, "zzz", "RSA-5")
    await _district(session, "phl", "CMX-3")
    await session.flush()


async def test_comps_never_cross_markets(db_session: AsyncSession) -> None:
    await _plant_two_markets(db_session)
    result = await value_parcel(db_session, "zzz:S", vacant_only=True)
    assert result is not None
    keys = {comp.parcel_number for comp in result.comps}
    assert keys == {"zzz:C"}
    assert "phl:C" not in keys


async def test_assemblage_never_crosses_markets(db_session: AsyncSession) -> None:
    await _plant_two_markets(db_session)
    result = await compute_assemblage(db_session, "zzz:S")
    assert result is not None
    keys = {n.parcel_number for n in result.neighbors}
    assert "zzz:N" in keys
    assert "phl:N" not in keys


async def test_street_access_never_crosses_markets(db_session: AsyncSession) -> None:
    await _plant_two_markets(db_session)
    assert await _has_street_frontage(db_session, "zzz:S") is False


async def test_area_search_never_crosses_markets(db_session: AsyncSession) -> None:
    await _plant_two_markets(db_session)
    centroid = (
        await db_session.execute(
            text(
                "SELECT ST_X(ST_Centroid(geom_4326)) AS lng, ST_Y(ST_Centroid(geom_4326)) AS lat "
                "FROM parcel WHERE parcel_number = 'zzz:S'"
            )
        )
    ).one()

    results, _ = await search_area(
        db_session,
        AreaSearchRequest(
            market="zzz", center=GeoPoint(lng=centroid.lng, lat=centroid.lat), radius_m=1000
        ),
    )
    keys = {r.parcel_number for r in results}
    assert keys
    assert all(key.startswith("zzz:") for key in keys)
    assert not any(key.startswith("phl:") for key in keys)


async def test_zzz_verdict_computes_without_touching_phl(db_session: AsyncSession) -> None:
    await _plant_two_markets(db_session)
    verdict = await compute_verdict(db_session, "zzz:S")
    assert verdict is not None
    assert "RSA-5" in verdict.summary or verdict.by_right_units is not None
    assert "CMX" not in verdict.summary
