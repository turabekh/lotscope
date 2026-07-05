import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_b1_migration_seeds_philadelphia_market(db_session: AsyncSession) -> None:
    row = (
        await db_session.execute(
            text(
                "SELECT code, url_slug, state, local_srid, timezone, launch_status "
                "FROM market WHERE code = 'phl'"
            )
        )
    ).one()
    assert row.url_slug == "philadelphia"
    assert row.state == "PA"
    assert row.local_srid == 2272
    assert row.timezone == "America/New_York"
    assert row.launch_status == "live"


async def test_parcel_gets_default_market_and_generated_local_key(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('phl:000000099')"))
    await db_session.flush()
    row = (
        await db_session.execute(
            text("SELECT market_code, local_key FROM parcel WHERE parcel_number = 'phl:000000099'")
        )
    ).one()
    assert row.market_code == "phl"
    assert row.local_key == "000000099"


async def test_parcel_market_code_is_foreign_keyed(db_session: AsyncSession) -> None:
    from sqlalchemy.exc import IntegrityError

    stmt = text("INSERT INTO parcel (parcel_number, market_code) VALUES ('zzz:1', 'zzz')")
    with pytest.raises(IntegrityError):
        await db_session.execute(stmt)
