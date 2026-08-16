import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.verdict.jobs import _parcel_numbers, recompute_all_verdicts
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


async def test_only_stale_skips_parcels_already_at_the_current_version(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code) "
            "VALUES ('stale-1','phl'), ('current-1','phl')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_verdict (parcel_number, verdict_version, computed_at) "
            "VALUES ('stale-1','v0', now()), ('current-1', :version, now())"
        ),
        {"version": VERDICT_VERSION},
    )
    await db_session.flush()

    stale = await _parcel_numbers(db_session, vacant_only=False, market="phl", only_stale=True)
    everything = await _parcel_numbers(db_session, vacant_only=False, market="phl")

    assert "stale-1" in stale
    assert "current-1" not in stale
    assert {"stale-1", "current-1"} <= set(everything)
