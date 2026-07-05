import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "parcel",
    "zoning_district",
    "zoning_standard",
    "sale",
    "tax_status",
    "li_event",
    "parcel_verdict",
}

EXPECTED_GIST_INDEXES = {
    "idx_parcel_geom_local",
    "idx_parcel_geom_4326",
    "idx_zoning_district_geom_local",
    "idx_zoning_district_geom_4326",
}


async def test_migration_creates_all_tables(db_connection: AsyncConnection) -> None:
    result = await db_connection.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    )
    tables = {row[0] for row in result}
    assert tables >= EXPECTED_TABLES


async def test_geometry_columns_have_gist_indexes(db_connection: AsyncConnection) -> None:
    result = await db_connection.execute(
        text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexdef ILIKE '%USING gist%'"
        )
    )
    indexes = {row[0] for row in result}
    assert indexes >= EXPECTED_GIST_INDEXES


async def test_geometry_round_trip_preserves_srid_and_area(
    db_connection: AsyncConnection,
) -> None:
    await db_connection.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_local, geom_4326) VALUES "
            "(:pn, ST_GeomFromText(:g2272, 2272), ST_GeomFromText(:g4326, 4326))"
        ),
        {
            "pn": "001",
            "g2272": "POLYGON((0 0, 0 10, 10 10, 10 0, 0 0))",
            "g4326": "POLYGON((-75 39, -75 40, -74 40, -74 39, -75 39))",
        },
    )
    result = await db_connection.execute(
        text(
            "SELECT ST_SRID(geom_local), ST_Area(geom_local), ST_SRID(geom_4326) "
            "FROM parcel WHERE parcel_number = :pn"
        ),
        {"pn": "001"},
    )
    srid_2272, area_2272, srid_4326 = result.one()
    assert srid_2272 == 2272
    assert area_2272 == pytest.approx(100.0)
    assert srid_4326 == 4326


async def test_foreign_key_cascade_deletes_children(db_connection: AsyncConnection) -> None:
    await db_connection.execute(
        text("INSERT INTO parcel (parcel_number) VALUES (:pn)"), {"pn": "777"}
    )
    await db_connection.execute(
        text("INSERT INTO sale (parcel_number, sale_price) VALUES (:pn, 1000)"),
        {"pn": "777"},
    )
    await db_connection.execute(text("DELETE FROM parcel WHERE parcel_number = :pn"), {"pn": "777"})
    result = await db_connection.execute(
        text("SELECT count(*) FROM sale WHERE parcel_number = :pn"), {"pn": "777"}
    )
    assert result.scalar_one() == 0
