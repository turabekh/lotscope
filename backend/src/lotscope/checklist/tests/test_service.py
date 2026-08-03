import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.checklist.service import build_parcel_checklist
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


async def _insert_parcel(session: AsyncSession, parcel_number: str, base_zoning_code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "market_value, base_zoning_code, geom_local) VALUES "
            "(:parcel_number, 1600, 18, 90, 150000, :base_zoning_code, "
            "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        ),
        {"parcel_number": parcel_number, "base_zoning_code": base_zoning_code},
    )


async def _setup(session: AsyncSession) -> None:
    await seed_zoning_standards(session)
    await session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await session.flush()


async def test_checklist_reports_high_confidence_for_a_corroborated_parcel(
    db_session: AsyncSession,
) -> None:
    await _setup(db_session)
    await _insert_parcel(db_session, "000000101", "RSA-5")
    await db_session.flush()

    checklist = await build_parcel_checklist(db_session, "000000101")

    assert checklist is not None
    assert checklist.buildability_confidence == "high"
    assert checklist.buildability_confidence_reasons == []


async def test_checklist_explains_why_confidence_is_not_high(db_session: AsyncSession) -> None:
    await _setup(db_session)
    await _insert_parcel(db_session, "000000102", "CMX-2")
    await db_session.flush()

    checklist = await build_parcel_checklist(db_session, "000000102")

    assert checklist is not None
    assert checklist.buildability_confidence == "medium"
    assert any(
        "no second source confirms" in reason
        for reason in checklist.buildability_confidence_reasons
    )
