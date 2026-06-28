import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.reports.service import build_parcel_dossier
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


async def test_build_dossier_returns_pdf(db_session: AsyncSession) -> None:
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, owner, lot_area_sqft, frontage_ft, "
            "depth_ft, base_zoning_code, geom_2272) VALUES "
            "('000000001', '1 Main St', 'OWNER A', 1600, 18, 90, 'RSA-5', "
            "ST_GeomFromText('POLYGON((0 0,0 90,18 90,18 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    pdf = await build_parcel_dossier(db_session, "000000001")
    assert pdf is not None
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


async def test_build_dossier_missing_parcel(db_session: AsyncSession) -> None:
    assert await build_parcel_dossier(db_session, "999999999") is None
