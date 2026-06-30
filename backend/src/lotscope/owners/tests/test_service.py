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


async def _seed_variants(session: AsyncSession) -> None:
    rows = [
        ("000000010", "SMITH, JOHN", True, 100000),
        ("000000011", "SMITH JOHN", True, 200000),
        ("000000012", "SMITH  JOHN", False, 300000),
        ("000000013", "ABC Properties, L.L.C.", True, 400000),
        ("000000014", "ABC PROPERTIES LLC", True, 500000),
        ("000000015", "SMITH JOHNSON", True, 999999),
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


async def test_portfolio_groups_across_punctuation_and_spacing(db_session: AsyncSession) -> None:
    await _seed_variants(db_session)
    portfolio = await get_owner_portfolio(db_session, "000000010")
    assert portfolio is not None
    assert portfolio.total_count == 3
    assert portfolio.vacant_count == 2
    assert portfolio.total_market_value == 600000
    others = [p.parcel_number for p in portfolio.parcels]
    assert others == ["000000012", "000000011"]


async def test_portfolio_groups_entity_suffix_variants(db_session: AsyncSession) -> None:
    await _seed_variants(db_session)
    portfolio = await get_owner_portfolio(db_session, "000000013")
    assert portfolio is not None
    assert portfolio.total_count == 2
    assert [p.parcel_number for p in portfolio.parcels] == ["000000014"]


async def test_portfolio_does_not_merge_distinct_owners(db_session: AsyncSession) -> None:
    await _seed_variants(db_session)
    portfolio = await get_owner_portfolio(db_session, "000000015")
    assert portfolio is not None
    assert portfolio.total_count == 1
    assert portfolio.parcels == []


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


async def test_portfolio_blank_owner_does_not_group(db_session: AsyncSession) -> None:
    for parcel_number in ("000000020", "000000021"):
        await db_session.execute(
            text("INSERT INTO parcel (parcel_number, owner) VALUES (:pn, '###')"),
            {"pn": parcel_number},
        )
    await db_session.flush()
    portfolio = await get_owner_portfolio(db_session, "000000020")
    assert portfolio is not None
    assert portfolio.total_count == 1
    assert portfolio.parcels == []


async def test_portfolio_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await get_owner_portfolio(db_session, "999999999") is None
