import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.historic.service import get_parcel_historic

pytestmark = pytest.mark.integration


async def _add_district(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO historic_district (external_id, name, designated_date, geom_local) VALUES "
            "('1', 'Old City', '2003-12-21', "
            "ST_GeomFromText('POLYGON((0 0,0 100,100 100,100 0,0 0))', 2272))"
        )
    )


async def test_parcel_inside_district_is_flagged(db_session: AsyncSession) -> None:
    await _add_district(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_local) VALUES "
            "('000000001', ST_GeomFromText('POLYGON((10 10,10 20,20 20,20 10,10 10))', 2272))"
        )
    )
    await db_session.flush()

    result = await get_parcel_historic(db_session, "000000001")
    assert result is not None
    assert result.in_historic_district is True
    assert result.district_name == "Old City"
    assert result.note is not None


async def test_parcel_outside_district_is_not_flagged(db_session: AsyncSession) -> None:
    await _add_district(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_local) VALUES ('000000002', "
            "ST_GeomFromText('POLYGON((500 500,500 510,510 510,510 500,500 500))', 2272))"
        )
    )
    await db_session.flush()

    result = await get_parcel_historic(db_session, "000000002")
    assert result is not None
    assert result.in_historic_district is False
    assert result.district_name is None
    assert result.note is None


async def test_parcel_without_geometry_is_not_flagged(db_session: AsyncSession) -> None:
    await _add_district(db_session)
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000003')"))
    await db_session.flush()

    result = await get_parcel_historic(db_session, "000000003")
    assert result is not None
    assert result.in_historic_district is False


async def test_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await get_parcel_historic(db_session, "999999999") is None
