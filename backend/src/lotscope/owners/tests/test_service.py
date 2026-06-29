import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.owners.service import get_owner_portfolio

pytestmark = pytest.mark.integration


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("000000001", " Acme Holdings LLC", True, 100000),
        ("000000002", "ACME HOLDINGS LLC", True, 250000),
        ("000000003", "acme holdings llc", False, 50000),
        ("000000004", "Someone Else", True, 999999),
    ]
    for parcel_number, owner, vacant, value in rows:
        await session.execute(
            text(
                "INSERT INTO parcel (parcel_number, owner, is_vacant, market_value) "
                "VALUES (:pn, :owner, :v, :mv)"
            ),
            {"pn": parcel_number, "owner": owner, "v": vacant, "mv": value},
        )
    await session.flush()


async def test_portfolio_groups_owner_case_insensitively(db_session: AsyncSession) -> None:
    await _seed(db_session)
    portfolio = await get_owner_portfolio(db_session, "000000001")
    assert portfolio is not None
    assert portfolio.total_count == 3
    assert portfolio.vacant_count == 2
    assert portfolio.total_market_value == 400000
    assert portfolio.shown == 2
    others = [p.parcel_number for p in portfolio.parcels]
    assert "000000001" not in others
    assert others == ["000000002", "000000003"]


async def test_portfolio_excludes_other_owners(db_session: AsyncSession) -> None:
    await _seed(db_session)
    portfolio = await get_owner_portfolio(db_session, "000000004")
    assert portfolio is not None
    assert portfolio.total_count == 1
    assert portfolio.parcels == []


async def test_portfolio_handles_missing_owner(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000009')"))
    await db_session.flush()
    portfolio = await get_owner_portfolio(db_session, "000000009")
    assert portfolio is not None
    assert portfolio.owner is None
    assert portfolio.total_count == 1
    assert portfolio.parcels == []


async def test_portfolio_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await get_owner_portfolio(db_session, "999999999") is None
