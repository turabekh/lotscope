import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.markets import MARKET_CODES
from lotscope.zoning.seed import _MARKET_SEEDERS, seed_all_zoning_standards


def test_every_registered_market_has_a_zoning_seeder() -> None:
    assert set(_MARKET_SEEDERS) == MARKET_CODES


@pytest.mark.integration
async def test_seed_all_covers_every_market(db_session: AsyncSession) -> None:
    seeded = await seed_all_zoning_standards(db_session)
    await db_session.flush()

    assert set(seeded) == MARKET_CODES
    assert all(count > 0 for count in seeded.values())

    rows = (
        await db_session.execute(
            text("SELECT market_code, count(*) FROM zoning_standard GROUP BY market_code")
        )
    ).all()
    assert {row[0] for row in rows} == MARKET_CODES


@pytest.mark.integration
async def test_seed_all_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_all_zoning_standards(db_session)
    await db_session.flush()
    second = await seed_all_zoning_standards(db_session)
    await db_session.flush()

    assert first == second
    total = await db_session.scalar(text("SELECT count(*) FROM zoning_standard"))
    assert total == sum(first.values())
