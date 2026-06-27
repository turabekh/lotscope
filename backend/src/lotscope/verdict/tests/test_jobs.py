import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.verdict.jobs import recompute_all_verdicts
from lotscope.verdict.models import ParcelVerdict

pytestmark = pytest.mark.integration

_PARCELS = ["900000001", "900000002"]


async def test_recompute_all_verdicts_persists_every_parcel(migrated_database: str) -> None:
    engine = create_async_engine(migrated_database)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            for parcel_number in _PARCELS:
                await session.execute(
                    text(
                        "INSERT INTO parcel (parcel_number, base_zoning_code) VALUES (:pn, 'RSA-5')"
                    ),
                    {"pn": parcel_number},
                )
            await session.commit()

        processed = await recompute_all_verdicts(session_factory, batch_size=1)
        assert processed >= len(_PARCELS)

        async with session_factory() as session:
            stored = await session.scalar(
                select(func.count())
                .select_from(ParcelVerdict)
                .where(ParcelVerdict.parcel_number.in_(_PARCELS))
            )
            versions = await session.scalars(
                select(ParcelVerdict.verdict_version).where(
                    ParcelVerdict.parcel_number.in_(_PARCELS)
                )
            )
            assert stored == len(_PARCELS)
            assert set(versions) == {VERDICT_VERSION}
    finally:
        async with session_factory() as session:
            await session.execute(
                text("DELETE FROM parcel_verdict WHERE parcel_number = ANY(:pns)"),
                {"pns": _PARCELS},
            )
            await session.execute(
                text("DELETE FROM parcel WHERE parcel_number = ANY(:pns)"),
                {"pns": _PARCELS},
            )
            await session.commit()
        await engine.dispose()
