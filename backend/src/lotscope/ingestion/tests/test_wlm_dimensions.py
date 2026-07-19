import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.loaders.wlm import derive_wlm_lot_width

pytestmark = pytest.mark.integration


async def test_derive_wlm_lot_width_from_geometry(db_session: AsyncSession) -> None:
    # A 40 (wide) x 100 (deep) ft rectangle in DE State Plane (2235): width = 40 ft.
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, geom_local) VALUES "
            "('wlm:2600000001', 'wlm', ST_SetSRID(ST_GeomFromText("
            "'POLYGON((0 0,0 100,40 100,40 0,0 0))'), 2235))"
        )
    )
    await db_session.flush()

    updated = await derive_wlm_lot_width(db_session)
    await db_session.flush()

    assert updated == 1
    frontage = await db_session.scalar(
        text("SELECT frontage_ft FROM parcel WHERE parcel_number = 'wlm:2600000001'")
    )
    assert frontage is not None
    assert 39.0 <= float(frontage) <= 41.0


async def test_derive_wlm_lot_width_skips_rows_that_already_have_frontage(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, frontage_ft, geom_local) VALUES "
            "('wlm:2600000002', 'wlm', 22, ST_SetSRID(ST_GeomFromText("
            "'POLYGON((0 0,0 100,40 100,40 0,0 0))'), 2235))"
        )
    )
    await db_session.flush()

    await derive_wlm_lot_width(db_session)
    await db_session.flush()

    frontage = await db_session.scalar(
        text("SELECT frontage_ft FROM parcel WHERE parcel_number = 'wlm:2600000002'")
    )
    assert float(frontage) == 22.0
