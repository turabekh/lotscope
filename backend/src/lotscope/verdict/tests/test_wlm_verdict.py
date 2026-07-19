import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.verdict.models import ParcelVerdict
from lotscope.verdict.service import compute_verdict
from lotscope.zoning.seed_wlm import seed_wlm_zoning_standards

pytestmark = pytest.mark.integration

_GEOM = (
    "ST_SetSRID(ST_GeomFromText('POLYGON((614000 642000,614000 642050,"
    "614040 642050,614040 642000,614000 642000))'), 2235)"
)


async def _insert_wlm_r3_parcel(
    session: AsyncSession, parcel_number: str, *, lot_area: int, frontage: int
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, lot_area_sqft, frontage_ft, "
            f"market_value, base_zoning_code, geom_local) VALUES (:pn, 'wlm', :area, :front, "
            f"47700, 'R-3', {_GEOM})"
        ),
        {"pn": parcel_number, "area": lot_area, "front": frontage},
    )
    await session.flush()


async def test_wlm_verdict_composes_a_buildable_r3_lot(db_session: AsyncSession) -> None:
    await seed_wlm_zoning_standards(db_session)
    await _insert_wlm_r3_parcel(db_session, "wlm:2601320063", lot_area=2000, frontage=20)

    result = await compute_verdict(db_session, "wlm:2601320063")
    await db_session.flush()

    assert result is not None
    assert result.verdict_version == VERDICT_VERSION
    assert result.can_build_by_right is True
    assert result.by_right_units == 1
    assert "R-3" in result.summary

    stored = await db_session.get(ParcelVerdict, "wlm:2601320063")
    assert stored is not None
    assert stored.verdict_version == VERDICT_VERSION
    assert stored.computed_at is not None


async def test_wlm_verdict_flags_an_undersized_r3_lot(db_session: AsyncSession) -> None:
    await seed_wlm_zoning_standards(db_session)
    await _insert_wlm_r3_parcel(db_session, "wlm:2601320099", lot_area=1000, frontage=12)

    result = await compute_verdict(db_session, "wlm:2601320099")
    await db_session.flush()

    assert result is not None
    assert result.can_build_by_right is False
