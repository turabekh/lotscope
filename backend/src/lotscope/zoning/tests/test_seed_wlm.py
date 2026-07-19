from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.seed_wlm import WLM_STANDARDS, seed_wlm_zoning_standards


def _by_code() -> dict[str, dict[str, Any]]:
    return {r["code"]: r for r in WLM_STANDARDS}


def test_all_twenty_four_districts_authored() -> None:
    codes = {r["code"] for r in WLM_STANDARDS}
    assert len(codes) == 24
    assert {"R-1", "R-2", "R-2A", "R-3", "R-4", "R-5A", "R-5A1", "R-5B", "R-5C"} <= codes
    assert {"C-1", "C-2", "C-4", "M-1", "M-2", "W-1", "W-4", "O"} <= codes


def test_high_volume_residential_dimensional_minimums() -> None:
    rows = _by_code()
    assert rows["R-3"]["min_lot_area_sqft"] == 1600
    assert rows["R-3"]["min_lot_width_ft"] == 16
    assert rows["R-3"]["max_units"] == 1  # "One Family Row Houses" per the GIS district name
    assert rows["R-1"]["min_lot_area_sqft"] == 6500
    assert rows["R-1"]["max_units"] == 1
    assert rows["R-2"]["max_units"] == 2
    assert rows["R-4"]["min_lot_area_sqft"] == 1280


def test_commercial_min_lot_is_null_not_guessed() -> None:
    rows = _by_code()
    for code in ("C-1", "C-2", "C-4", "M-1", "M-2", "W-1", "O"):
        assert "min_lot_area_sqft" not in rows[code]
        assert "min_lot_width_ft" not in rows[code]
        assert "max_units" not in rows[code]


def test_far_recorded_where_height_is_unbounded() -> None:
    rows = _by_code()
    assert rows["C-4"]["max_floor_area_ratio_pct"] == 2000
    assert rows["R-5B"]["max_floor_area_ratio_pct"] == 350
    assert "max_height_ft" not in rows["C-4"]  # code prescribes no height, FAR governs


def test_every_row_has_a_primary_use() -> None:
    for row in WLM_STANDARDS:
        assert row["permitted_uses"]


@pytest.mark.integration
async def test_seed_wlm_upserts_and_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_wlm_zoning_standards(db_session)
    second = await seed_wlm_zoning_standards(db_session)
    await db_session.flush()

    assert first == 24
    assert second == 24
    count = await db_session.scalar(
        text("SELECT count(*) FROM zoning_standard WHERE market_code = 'wlm'")
    )
    assert count == 24
    r3 = (
        await db_session.execute(
            text(
                "SELECT min_lot_area_sqft, max_units, code_version FROM zoning_standard "
                "WHERE market_code = 'wlm' AND code = 'R-3'"
            )
        )
    ).one()
    assert float(r3[0]) == 1600.0
    assert r3[1] == 1
    assert r3[2] == "wlm-provisional-2026"


@pytest.mark.integration
async def test_buildability_resolves_the_wlm_standard_for_a_parcel(
    db_session: AsyncSession,
) -> None:
    from lotscope.zoning.service import get_parcel_standard

    await seed_wlm_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, base_zoning_code) "
            "VALUES ('wlm:2601320063', 'wlm', 'R-3')"
        )
    )
    await db_session.flush()

    standard = await get_parcel_standard(db_session, "wlm:2601320063")
    assert standard is not None
    assert standard.code == "R-3"
    assert standard.min_lot_area_sqft == 1600.0
    assert standard.max_units == 1
    assert standard.citation_label == "Wilmington Zoning Code (Ch. 48)"
