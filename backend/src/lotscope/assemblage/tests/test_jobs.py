from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assemblage.service import recompute_assemblage

pytestmark = pytest.mark.integration


async def _insert(
    session: AsyncSession,
    parcel_number: str,
    *,
    owner: str,
    zoning: str,
    polygon: str,
    is_vacant: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, base_zoning_code, lot_area_sqft, "
            "frontage_ft, is_vacant, geom_local) VALUES "
            "(:pn, :owner, :zoning, 1620, 18, :vacant, ST_GeomFromText(:poly, 2272))"
        ),
        {
            "pn": parcel_number,
            "owner": owner,
            "zoning": zoning,
            "vacant": is_vacant,
            "poly": polygon,
        },
    )


async def _row(session: AsyncSession, parcel_number: str) -> Row[Any] | None:
    return (
        await session.execute(
            text(
                "SELECT candidate_count, unit_unlock, potential, base_zoning_code "
                "FROM parcel_assemblage WHERE parcel_number = :pn"
            ),
            {"pn": parcel_number},
        )
    ).one_or_none()


async def test_recompute_persists_plays_and_skips_lone_lots(db_session: AsyncSession) -> None:
    await _insert(
        db_session,
        "000000001",
        owner="OWNER A",
        zoning="RSA-5",
        is_vacant=True,
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await _insert(
        db_session,
        "000000002",
        owner="OWNER A",
        zoning="RSA-5",
        polygon="POLYGON((18 0,18 90,36 90,36 0,18 0))",
    )
    await _insert(
        db_session,
        "000000009",
        owner="OWNER C",
        zoning="CMX-2",
        is_vacant=True,
        polygon="POLYGON((1000 1000,1000 1090,1018 1090,1018 1000,1000 1000))",
    )
    await db_session.flush()

    persisted = await recompute_assemblage(db_session, ["000000001", "000000009"])
    assert persisted == 1

    play = await _row(db_session, "000000001")
    assert play is not None
    assert play.candidate_count == 1
    assert play.base_zoning_code == "RSA-5"

    assert await _row(db_session, "000000009") is None  # isolated vacant lot, no candidate


async def test_recompute_removes_a_parcel_that_no_longer_qualifies(
    db_session: AsyncSession,
) -> None:
    await _insert(
        db_session,
        "000000001",
        owner="OWNER A",
        zoning="RSA-5",
        is_vacant=True,
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await _insert(
        db_session,
        "000000002",
        owner="OWNER A",
        zoning="RSA-5",
        polygon="POLYGON((18 0,18 90,36 90,36 0,18 0))",
    )
    await db_session.flush()

    await recompute_assemblage(db_session, ["000000001"])
    assert await _row(db_session, "000000001") is not None

    await db_session.execute(text("DELETE FROM parcel WHERE parcel_number = '000000002'"))
    await db_session.flush()

    await recompute_assemblage(db_session, ["000000001"])
    assert await _row(db_session, "000000001") is None
