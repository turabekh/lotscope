import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assemblage.service import compute_assemblage
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


async def _insert(
    session: AsyncSession,
    parcel_number: str,
    *,
    owner: str,
    zoning: str,
    polygon: str,
    is_vacant: bool = False,
    is_city_owned: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, base_zoning_code, lot_area_sqft, "
            "frontage_ft, is_vacant, is_city_owned, geom_local) VALUES "
            "(:pn, :owner, :zoning, 1620, 18, :vacant, :city, "
            "ST_GeomFromText(:poly, 2272))"
        ),
        {
            "pn": parcel_number,
            "owner": owner,
            "zoning": zoning,
            "vacant": is_vacant,
            "city": is_city_owned,
            "poly": polygon,
        },
    )


async def test_assemblage_detects_adjacent_candidates(db_session: AsyncSession) -> None:
    await _insert(
        db_session,
        "000000001",
        owner="OWNER A",
        zoning="RSA-5",
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await _insert(
        db_session,
        "000000002",
        owner="OWNER A",
        zoning="RSA-5",
        polygon="POLYGON((-18 0,-18 90,0 90,0 0,-18 0))",
    )
    await _insert(
        db_session,
        "000000003",
        owner="OWNER B",
        zoning="RSA-5",
        is_vacant=True,
        polygon="POLYGON((18 0,18 90,36 90,36 0,18 0))",
    )
    await _insert(
        db_session,
        "000000004",
        owner="CITY OF PHILADELPHIA",
        zoning="RSA-5",
        is_city_owned=True,
        polygon="POLYGON((0 90,0 180,18 180,18 90,0 90))",
    )
    await _insert(
        db_session,
        "000000009",
        owner="OWNER C",
        zoning="CMX-2",
        polygon="POLYGON((1000 1000,1000 1090,1018 1090,1018 1000,1000 1000))",
    )
    await db_session.flush()

    result = await compute_assemblage(db_session, "000000001")
    assert result is not None

    numbers = {n.parcel_number for n in result.neighbors}
    assert numbers == {"000000002", "000000003", "000000004"}

    by_number = {n.parcel_number: n for n in result.neighbors}
    assert by_number["000000002"].acquirability == "same_owner"
    assert by_number["000000003"].acquirability == "vacant"
    assert by_number["000000004"].acquirability == "city_owned"
    assert all(n.is_candidate for n in result.neighbors)

    assert result.potential == "high"
    assert result.summary.candidate_count == 3
    assert result.summary.combined_lot_area_sqft == 6480.0


async def test_assemblage_estimates_combined_units_for_density_district(
    db_session: AsyncSession,
) -> None:
    await seed_zoning_standards(db_session)
    await _insert(
        db_session,
        "000000001",
        owner="OWNER A",
        zoning="RM-1",
        is_vacant=True,
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await _insert(
        db_session,
        "000000002",
        owner="OWNER B",
        zoning="RM-1",
        is_vacant=True,
        polygon="POLYGON((18 0,18 90,36 90,36 0,18 0))",
    )
    await db_session.flush()

    result = await compute_assemblage(db_session, "000000001")
    assert result is not None
    assert result.summary.units_basis == "per_unit"
    assert result.summary.by_right_units_current == 3
    assert result.summary.by_right_units_combined == 6


async def test_assemblage_estimates_combined_units_for_far_district(
    db_session: AsyncSession,
) -> None:
    await seed_zoning_standards(db_session)
    await _insert(
        db_session,
        "000000001",
        owner="OWNER A",
        zoning="RM-4",
        is_vacant=True,
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await _insert(
        db_session,
        "000000002",
        owner="OWNER B",
        zoning="RM-4",
        is_vacant=True,
        polygon="POLYGON((18 0,18 90,36 90,36 0,18 0))",
    )
    await db_session.flush()

    result = await compute_assemblage(db_session, "000000001")
    assert result is not None
    assert result.summary.units_basis == "far_estimate"
    assert result.summary.by_right_units_combined is not None
    assert result.summary.by_right_units_current is not None
    assert result.summary.by_right_units_combined > result.summary.by_right_units_current


async def test_assemblage_missing_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await compute_assemblage(db_session, "999999999") is None


async def test_assemblage_isolated_lot_has_no_neighbors(db_session: AsyncSession) -> None:
    await _insert(
        db_session,
        "000000005",
        owner="SOLO",
        zoning="RSA-5",
        polygon="POLYGON((0 0,0 90,18 90,18 0,0 0))",
    )
    await db_session.flush()

    result = await compute_assemblage(db_session, "000000005")
    assert result is not None
    assert result.neighbors == []
    assert result.potential == "none"
