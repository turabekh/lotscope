import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.models import ZoningStandard
from lotscope.zoning.seed import TITLE_14_STANDARDS, TITLE_14_VERSION, seed_zoning_standards
from lotscope.zoning.service import assess_parcel


def test_seed_entries_are_well_formed() -> None:
    codes = [entry["code"] for entry in TITLE_14_STANDARDS]
    assert len(codes) == len(set(codes))
    for entry in TITLE_14_STANDARDS:
        assert entry["code"]
        assert entry["permitted_uses"]


@pytest.mark.integration
async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_zoning_standards(db_session)
    await db_session.flush()
    second = await seed_zoning_standards(db_session)
    await db_session.flush()

    assert first == len(TITLE_14_STANDARDS)
    assert second == len(TITLE_14_STANDARDS)
    count = await db_session.scalar(
        select(func.count())
        .select_from(ZoningStandard)
        .where(ZoningStandard.code_version == TITLE_14_VERSION)
    )
    assert count == len(TITLE_14_STANDARDS)


@pytest.mark.integration
async def test_seeded_standard_drives_buildability(db_session: AsyncSession) -> None:
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code) VALUES ('000000001', 1600, 18, 90, 'RSA-5')"
        )
    )
    await db_session.flush()

    result = await assess_parcel(db_session, "000000001")
    assert result is not None
    assert result.district_code == "RSA-5"
    assert result.can_build_by_right is True
    assert result.by_right_units == 1
    assert result.cited_section is not None
    assert TITLE_14_VERSION in result.cited_section
