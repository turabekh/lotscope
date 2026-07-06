import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.seed_hbg import HBG_STANDARDS, seed_hbg_zoning_standards
from lotscope.zoning.service import _get_standard


def _by_code() -> dict[str, dict[str, object]]:
    return {entry["code"]: entry for entry in HBG_STANDARDS}


def test_hbg_standards_transcribe_the_verbatim_table() -> None:
    codes = _by_code()
    assert set(codes) == {"OSR", "RL", "RM", "CN", "CG", "DC", "RF", "INS", "IND"}
    assert codes["RM"]["min_lot_area_sqft"] == 1500
    assert codes["RM"]["lot_area_per_unit_sqft"] == 1500
    assert codes["CG"]["max_height_ft"] == 100
    assert codes["OSR"]["max_occupancy_pct"] == 30


def test_conditional_rules_are_null_not_guessed() -> None:
    codes = _by_code()
    # Riverfront lot width / front / rear are location-conditional -> NULL, not a guess
    assert codes["RF"]["min_lot_width_ft"] is None
    assert codes["RF"]["front_setback_ft"] is None
    assert codes["RF"]["rear_setback_ft"] is None
    # DC and IND have no maximum height -> NULL
    assert codes["DC"]["max_height_ft"] is None
    assert codes["IND"]["max_height_ft"] is None
    # CN front is a build-to maximum, not a minimum -> 0 required
    assert codes["CN"]["front_setback_ft"] == 0


@pytest.mark.integration
async def test_standard_lookup_is_market_scoped(db_session: AsyncSession) -> None:
    await seed_hbg_zoning_standards(db_session)
    # a colliding phl 'RM' standard with a different figure
    await db_session.execute(
        text(
            "INSERT INTO zoning_standard (market_code, code, code_version, min_lot_area_sqft) "
            "VALUES ('phl', 'RM', 'phl-test', 9999)"
        )
    )
    await db_session.flush()

    hbg = await _get_standard(db_session, "RM", "hbg")
    phl = await _get_standard(db_session, "RM", "phl")
    assert hbg is not None
    assert hbg.min_lot_area_sqft == 1500
    assert phl is not None
    assert phl.min_lot_area_sqft == 9999
    assert await _get_standard(db_session, "RF", "phl") is None
    assert (await _get_standard(db_session, "RF", "hbg")) is not None
