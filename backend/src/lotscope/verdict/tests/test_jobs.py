import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lotscope.verdict.jobs import rebuild_all_screens

pytestmark = pytest.mark.integration

_PARCELS = ["900000001", "900000002"]


async def test_the_rebuild_covers_the_vacant_lots_and_leaves_the_rest(
    migrated_database: str,
) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            for parcel_number in _PARCELS:
                await session.execute(
                    text(
                        "INSERT INTO parcel (parcel_number, base_zoning_code, is_vacant, "
                        "geom_local) VALUES (:pn, 'RSA-5', TRUE, "
                        "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
                    ),
                    {"pn": parcel_number},
                )
            # A built parcel is not part of the screening universe, so the index skips it.
            await session.execute(
                text(
                    "INSERT INTO parcel (parcel_number, base_zoning_code, is_vacant, geom_local) "
                    "VALUES ('900000003', 'RSA-5', FALSE, "
                    "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
                )
            )
            await session.commit()

        written = await rebuild_all_screens(session_factory, batch_size=1)
        assert written >= len(_PARCELS)

        async with session_factory() as session:
            indexed = await session.scalar(
                text("SELECT count(*) FROM parcel_screen WHERE parcel_number = ANY(:pns)"),
                {"pns": [*_PARCELS, "900000003"]},
            )
            stamped = await session.scalar(
                text(
                    "SELECT count(*) FROM parcel_screen WHERE parcel_number = ANY(:pns) "
                    "AND computed_at IS NOT NULL"
                ),
                {"pns": _PARCELS},
            )
        assert indexed == len(_PARCELS)
        assert stamped == len(_PARCELS)
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM parcel WHERE parcel_number = ANY(:pns)"),
                {"pns": [*_PARCELS, "900000003"]},
            )
            await session.commit()
        await engine.dispose()


async def test_the_rebuild_replaces_what_it_wrote_last_night(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO parcel (parcel_number, base_zoning_code, is_vacant, geom_local) "
                    "VALUES ('900000004', 'RSA-5', TRUE, "
                    "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
                )
            )
            await session.execute(
                text(
                    "INSERT INTO parcel_screen (parcel_number, opportunity_score, computed_at) "
                    "VALUES ('900000004', 1, now() - interval '2 days')"
                )
            )
            await session.commit()

        await rebuild_all_screens(session_factory)

        async with session_factory() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT opportunity_score, computed_at FROM parcel_screen "
                        "WHERE parcel_number = '900000004'"
                    )
                )
            ).one()
        assert row.opportunity_score != 1
        assert row.computed_at is not None
    finally:
        async with session_factory() as session:
            await session.execute(text("DELETE FROM parcel WHERE parcel_number = '900000004'"))
            await session.commit()
        await engine.dispose()
