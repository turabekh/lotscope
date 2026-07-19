import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.loaders.wlm import derive_wlm_vacancy

pytestmark = pytest.mark.integration


async def test_derive_wlm_vacancy_flags_parcels_without_a_structure(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, improvement_value) VALUES "
            "('wlm:2600000010', 'wlm', 0),"  # no structure -> vacant
            "('wlm:2600000011', 'wlm', NULL),"  # no structure value -> vacant
            "('wlm:2600000012', 'wlm', 33400),"  # has a structure -> not vacant
            "('phl:000000001', 'phl', 0)"  # other market -> untouched
        )
    )
    await db_session.flush()

    vacant = await derive_wlm_vacancy(db_session)
    await db_session.flush()

    assert vacant == 2
    result = (
        await db_session.execute(
            text(
                "SELECT parcel_number, is_vacant FROM parcel "
                "WHERE parcel_number LIKE 'wlm:%' ORDER BY parcel_number"
            )
        )
    ).all()
    rows: dict[str, bool] = {row[0]: row[1] for row in result}
    assert rows["wlm:2600000010"] is True
    assert rows["wlm:2600000011"] is True
    assert rows["wlm:2600000012"] is False

    conf = await db_session.scalar(
        text("SELECT vacancy_confidence FROM parcel WHERE parcel_number = 'wlm:2600000010'")
    )
    assert float(conf) == 0.35

    # other markets are not touched
    phl_vacant = await db_session.scalar(
        text("SELECT is_vacant FROM parcel WHERE parcel_number = 'phl:000000001'")
    )
    assert phl_vacant is None
