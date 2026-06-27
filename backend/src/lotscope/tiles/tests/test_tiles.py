import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.tiles.layers import PARCELS_FUNCTION, VACANT_LOTS_FUNCTION

pytestmark = pytest.mark.integration

_POLYGON = "POLYGON((-75.16 39.95, -75.16 39.951, -75.159 39.951, -75.159 39.95, -75.16 39.95))"
_ZOOM = 16


async def _insert_parcel(session: AsyncSession, parcel_number: str, *, vacant: bool) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, is_vacant, geom_4326) "
            "VALUES (:pn, '123 MAIN ST', :vacant, ST_GeomFromText(:geom, 4326))"
        ),
        {"pn": parcel_number, "vacant": vacant, "geom": _POLYGON},
    )


async def _covering_tile(session: AsyncSession) -> tuple[int, int]:
    result = await session.execute(
        text(
            "WITH pt AS (SELECT ST_Centroid(ST_GeomFromText(:geom, 4326)) AS g) "
            "SELECT floor((ST_X(g) + 180) / 360 * (2 ^ :z))::int AS x, "
            "floor((1 - ln(tan(radians(ST_Y(g))) + 1 / cos(radians(ST_Y(g)))) / pi()) "
            "/ 2 * (2 ^ :z))::int AS y "
            "FROM pt"
        ),
        {"geom": _POLYGON, "z": _ZOOM},
    )
    x, y = result.one()
    return int(x), int(y)


async def test_parcels_tile_has_data_only_where_geometry_falls(db_session: AsyncSession) -> None:
    await _insert_parcel(db_session, "000000001", vacant=False)
    await db_session.flush()
    x, y = await _covering_tile(db_session)

    covering = await db_session.scalar(
        text(f"SELECT length({PARCELS_FUNCTION}({_ZOOM}, {x}, {y}))")
    )
    elsewhere = await db_session.scalar(
        text(f"SELECT length({PARCELS_FUNCTION}({_ZOOM}, {x + 5}, {y + 5}))")
    )

    assert covering is not None
    assert covering > 0
    assert elsewhere == 0


async def test_vacant_lots_tile_filters_to_vacant(db_session: AsyncSession) -> None:
    await _insert_parcel(db_session, "000000001", vacant=False)
    await db_session.flush()
    x, y = await _covering_tile(db_session)

    before = await db_session.scalar(
        text(f"SELECT length({VACANT_LOTS_FUNCTION}({_ZOOM}, {x}, {y}))")
    )
    assert before == 0

    await _insert_parcel(db_session, "000000002", vacant=True)
    await db_session.flush()
    after = await db_session.scalar(
        text(f"SELECT length({VACANT_LOTS_FUNCTION}({_ZOOM}, {x}, {y}))")
    )
    assert after is not None
    assert after > 0
