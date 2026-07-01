import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ValidationError
from lotscope.search.schemas import AreaSearchRequest, GeoPoint
from lotscope.search.spatial import build_filters, search_area


def test_request_rejects_multiple_shapes() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        AreaSearchRequest(
            center=GeoPoint(lat=39.95, lng=-75.16),
            radius_m=500,
            polygon={"type": "Polygon", "coordinates": []},
        )


def test_request_rejects_no_shape() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        AreaSearchRequest()


def test_request_accepts_radius_only() -> None:
    request = AreaSearchRequest(center=GeoPoint(lat=39.95, lng=-75.16), radius_m=500)
    assert request.radius_m == 500


def test_request_accepts_polygon_only() -> None:
    request = AreaSearchRequest(polygon={"type": "Polygon", "coordinates": []})
    assert request.polygon is not None


def test_request_accepts_neighborhood_only() -> None:
    request = AreaSearchRequest(neighborhood="Fishtown")
    assert request.neighborhood == "Fishtown"


def test_build_filters_default_requires_geometry() -> None:
    where, params = build_filters(vacant_only=False, zoning_codes=[])
    assert where == "p.geom_4326 IS NOT NULL"
    assert params == {}


def test_build_filters_vacant_and_zoning_normalized() -> None:
    where, params = build_filters(vacant_only=True, zoning_codes=[" rsa5 ", "rm1", ""])
    assert "coalesce(p.is_vacant, false) = true" in where
    assert "p.base_zoning_code = ANY(:zoning_codes)" in where
    assert params["zoning_codes"] == ["RSA5", "RM1"]


def test_build_filters_buy_box_criteria() -> None:
    where, params = build_filters(
        vacant_only=False,
        zoning_codes=[],
        min_lot_area_sqft=1000,
        max_lot_area_sqft=5000,
        min_market_value=50000,
        max_market_value=300000,
        min_opportunity_score=60,
    )
    assert "p.lot_area_sqft >= :min_lot_area" in where
    assert "p.lot_area_sqft <= :max_lot_area" in where
    assert "p.market_value >= :min_value" in where
    assert "p.market_value <= :max_value" in where
    assert "pv.opportunity_score >= :min_score" in where
    assert params == {
        "min_lot_area": 1000,
        "max_lot_area": 5000,
        "min_value": 50000,
        "max_value": 300000,
        "min_score": 60,
    }


def test_build_filters_omits_unset_criteria() -> None:
    where, params = build_filters(vacant_only=False, zoning_codes=[], min_opportunity_score=70)
    assert "pv.opportunity_score >= :min_score" in where
    assert "lot_area" not in where
    assert "market_value" not in where
    assert params == {"min_score": 70}


def _square(lng: float, lat: float, size: float = 0.0001) -> str:
    points = [
        (lng - size, lat - size),
        (lng + size, lat - size),
        (lng + size, lat + size),
        (lng - size, lat + size),
        (lng - size, lat - size),
    ]
    ring = ", ".join(f"{x} {y}" for x, y in points)
    return f"POLYGON(({ring}))"


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("000000001", "RSA5", True, _square(-75.1600, 39.9500)),
        ("000000002", "RM1", False, _square(-75.1600, 39.9520)),
        ("000000003", "RSA5", True, _square(-75.1600, 39.9700)),
    ]
    for parcel_number, zoning, vacant, wkt in rows:
        await session.execute(
            text(
                "INSERT INTO parcel (parcel_number, base_zoning_code, is_vacant, geom_4326) "
                "VALUES (:pn, :z, :v, ST_GeomFromText(:wkt, 4326))"
            ),
            {"pn": parcel_number, "z": zoning, "v": vacant, "wkt": wkt},
        )
    await session.flush()


@pytest.mark.integration
async def test_radius_returns_near_parcels_ordered_by_distance(db_session: AsyncSession) -> None:
    await _seed(db_session)

    request = AreaSearchRequest(center=GeoPoint(lat=39.9500, lng=-75.1600), radius_m=500)
    results, total = await search_area(db_session, request)

    assert total == 2
    assert [r.parcel_number for r in results] == ["000000001", "000000002"]
    first, second = results[0], results[1]
    assert first.distance_m is not None
    assert second.distance_m is not None
    assert first.distance_m <= second.distance_m
    assert first.lat is not None
    assert first.lng is not None


@pytest.mark.integration
async def test_radius_respects_vacant_and_zoning_filters(db_session: AsyncSession) -> None:
    await _seed(db_session)

    vacant, vacant_total = await search_area(
        db_session,
        AreaSearchRequest(
            center=GeoPoint(lat=39.9500, lng=-75.1600), radius_m=500, vacant_only=True
        ),
    )
    assert vacant_total == 1
    assert [r.parcel_number for r in vacant] == ["000000001"]

    zoned, zoned_total = await search_area(
        db_session,
        AreaSearchRequest(
            center=GeoPoint(lat=39.9500, lng=-75.1600), radius_m=500, zoning_codes=["RM1"]
        ),
    )
    assert zoned_total == 1
    assert [r.parcel_number for r in zoned] == ["000000002"]


@pytest.mark.integration
async def test_polygon_returns_intersecting_parcels(db_session: AsyncSession) -> None:
    await _seed(db_session)

    polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [-75.162, 39.949],
                [-75.158, 39.949],
                [-75.158, 39.953],
                [-75.162, 39.953],
                [-75.162, 39.949],
            ]
        ],
    }
    results, total = await search_area(db_session, AreaSearchRequest(polygon=polygon))
    assert total == 2
    assert sorted(r.parcel_number for r in results) == ["000000001", "000000002"]
    assert all(r.distance_m is None for r in results)

    capped, capped_total = await search_area(
        db_session, AreaSearchRequest(polygon=polygon, limit=1)
    )
    assert len(capped) == 1
    assert capped_total == 2


@pytest.mark.integration
async def test_polygon_rejects_non_polygon_geometry(db_session: AsyncSession) -> None:
    request = AreaSearchRequest(polygon={"type": "Point", "coordinates": [-75.16, 39.95]})
    with pytest.raises(ValidationError):
        await search_area(db_session, request)


@pytest.mark.integration
async def test_neighborhood_returns_parcels_inside_boundary(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await db_session.execute(
        text(
            "INSERT INTO neighborhood (external_id, name, geom_4326) "
            "VALUES ('1', 'Test Park', ST_GeomFromText(:wkt, 4326))"
        ),
        {"wkt": _square(-75.1600, 39.9510, size=0.0015)},
    )
    await db_session.flush()

    results, total = await search_area(db_session, AreaSearchRequest(neighborhood="Test Park"))
    assert total == 2
    assert sorted(r.parcel_number for r in results) == ["000000001", "000000002"]


@pytest.mark.integration
async def test_neighborhood_unknown_name_returns_empty(db_session: AsyncSession) -> None:
    await _seed(db_session)
    results, total = await search_area(db_session, AreaSearchRequest(neighborhood="Nowhere"))
    assert results == []
    assert total == 0
