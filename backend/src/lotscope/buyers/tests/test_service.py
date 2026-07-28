from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buyers.service import (
    buyers_near_parcel,
    get_buyer,
    list_buyers,
    recompute_buyer_profiles,
)

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 7, 1, tzinfo=UTC)


async def _parcel(
    session: AsyncSession,
    pn: str,
    x: float,
    y: float,
    *,
    market: str = "phl",
    vacant: bool = True,
    owner: str | None = None,
    mailing: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, is_vacant, owner, mailing_address, "
            "address, geom_local, geom_4326) VALUES "
            "(:pn, :m, :v, :owner, :mail, :addr, ST_SetSRID(ST_MakePoint(:x, :y), 2272), NULL)"
        ),
        {
            "pn": pn,
            "m": market,
            "v": vacant,
            "owner": owner,
            "mail": mailing,
            "addr": pn,
            "x": x,
            "y": y,
        },
    )


async def _sale(
    session: AsyncSession,
    pn: str,
    grantee: str,
    doc: str,
    *,
    grantor: str = "SELLER LLC",
    price: float = 5000.0,
    when: str = "2026-01-15",
) -> None:
    await session.execute(
        text(
            "INSERT INTO sale "
            "(parcel_number, document_id, sale_price, sale_date, grantor, grantee) "
            "VALUES (:pn, :doc, :price, :when, :grantor, :grantee)"
        ),
        {
            "pn": pn,
            "doc": doc,
            "price": price,
            "when": date.fromisoformat(when),
            "grantor": grantor,
            "grantee": grantee,
        },
    )


async def _buyer_purchases(
    session: AsyncSession, name: str, count: int, *, x: float = 1000.0, y: float = 1000.0, **kw: str
) -> None:
    for i in range(count):
        pn = f"phl:{name}:{i}"
        await _parcel(session, pn, x + i, y + i)
        await _sale(session, pn, name, f"DOC-{name}-{i}", **kw)  # type: ignore[arg-type]


async def test_recompute_derives_and_reads_qualifying_buyer(db_session: AsyncSession) -> None:
    await _buyer_purchases(db_session, "THEDOOR LLC", 3)
    await db_session.flush()

    count = await recompute_buyer_profiles(db_session, now=_NOW)
    assert count == 1

    roster = await list_buyers(db_session, "phl")
    assert roster.total == 1
    assert roster.buyers[0].buyer_key == "THEDOOR LLC"
    assert roster.buyers[0].lot_purchases_window == 3

    profile = await get_buyer(db_session, "phl", "THEDOOR LLC")
    assert profile is not None
    assert len(profile.purchases) == 3


async def test_future_dated_sale_never_counts_as_a_purchase(db_session: AsyncSession) -> None:
    await _buyer_purchases(db_session, "TIMELORD LLC", 3)
    await _parcel(db_session, "phl:future", 1100.0, 1100.0)
    await db_session.execute(
        text(
            "INSERT INTO sale "
            "(parcel_number, document_id, sale_price, sale_date, grantor, grantee) "
            "VALUES ('phl:future', 'DOC-FUTURE', 5000, CURRENT_DATE + 1, 'SELLER LLC', "
            "'TIMELORD LLC')"
        )
    )
    await db_session.flush()

    await recompute_buyer_profiles(db_session, now=_NOW)

    roster = await list_buyers(db_session, "phl")
    assert roster.buyers[0].lot_purchases_window == 3

    profile = await get_buyer(db_session, "phl", "TIMELORD LLC")
    assert profile is not None
    assert "phl:future" not in {p.parcel_number for p in profile.purchases}


async def test_exclusions_end_to_end(db_session: AsyncSession) -> None:
    await _buyer_purchases(db_session, "PHILADELPHIA LAND BANK", 4)
    await _buyer_purchases(db_session, "RELATED LLC", 2)
    await _parcel(db_session, "phl:rp", 5.0, 5.0)
    await _sale(db_session, "phl:rp", "RELATED LLC", "DOC-RP", grantor="RELATED LLC")
    for i in range(3):
        pn = f"phl:pkg:{i}"
        await _parcel(db_session, pn, 10.0 + i, 10.0 + i)
        await _sale(db_session, pn, "PKG LLC", "SHARED-DEED")
    await db_session.flush()

    count = await recompute_buyer_profiles(db_session, now=_NOW)
    assert count == 0


async def test_mailing_address_join_hit_and_miss(db_session: AsyncSession) -> None:
    await _buyer_purchases(db_session, "MAILME LLC", 3)
    await _parcel(
        db_session, "phl:owned", 5.0, 5.0, vacant=False, owner="MAILME LLC", mailing="1 PO BOX"
    )
    await _buyer_purchases(db_session, "NOMAIL LLC", 3, x=2000.0, y=2000.0)
    await db_session.flush()

    await recompute_buyer_profiles(db_session, now=_NOW)
    mailme = await get_buyer(db_session, "phl", "MAILME LLC")
    nomail = await get_buyer(db_session, "phl", "NOMAIL LLC")
    assert mailme is not None
    assert mailme.mailing_address == "1 PO BOX"
    assert nomail is not None
    assert nomail.mailing_address is None


async def test_revocation_when_buyer_ages_out(db_session: AsyncSession) -> None:
    await _buyer_purchases(db_session, "FADER LLC", 3)
    await db_session.flush()
    assert await recompute_buyer_profiles(db_session, now=_NOW) == 1

    await db_session.execute(text("DELETE FROM sale WHERE grantee = 'FADER LLC'"))
    await db_session.flush()
    assert await recompute_buyer_profiles(db_session, now=_NOW) == 0
    assert (await list_buyers(db_session, "phl")).total == 0


async def test_near_parcel_ranks_by_proximity(db_session: AsyncSession) -> None:
    await _parcel(db_session, "phl:subject", 1000.0, 1000.0)
    await _buyer_purchases(db_session, "NEAR LLC", 3, x=1010.0, y=1010.0)
    await _buyer_purchases(db_session, "FAR LLC", 3, x=9000.0, y=9000.0)
    await db_session.flush()
    await recompute_buyer_profiles(db_session, now=_NOW)

    nearby = await buyers_near_parcel(db_session, "phl:subject", "phl")
    keys = [b.buyer_key for b in nearby.buyers]
    assert keys == ["NEAR LLC"]
    assert nearby.buyers[0].distance_ft < 2640.0
