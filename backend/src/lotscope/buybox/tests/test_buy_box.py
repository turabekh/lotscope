import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.schemas import (
    DEFAULT_EXCLUDE_FLOOD,
    DEFAULT_EXCLUDE_HISTORIC,
    DEFAULT_MIN_LOT_SQFT,
    DEFAULT_TARGET_USE,
    BuyBoxArea,
    BuyBoxWrite,
)
from lotscope.buybox.service import (
    OWNER_SOURCE,
    buy_box_assumptions,
    read_buy_box,
    seed_owned_parcels,
    write_buy_box,
)
from lotscope.core.errors import ValidationError

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:email, 'x', 'user', 'pro', true)"
        ),
        {"email": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def test_a_user_with_no_row_reads_the_documented_defaults(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "defaults@example.com")

    box = await read_buy_box(db_session, user_id)

    assert box.target_use == DEFAULT_TARGET_USE
    assert box.min_lot_sqft == DEFAULT_MIN_LOT_SQFT
    assert box.exclude_historic is DEFAULT_EXCLUDE_HISTORIC
    assert box.exclude_flood is DEFAULT_EXCLUDE_FLOOD
    assert box.areas == []
    assert box.zoning_codes == []
    assert box.assumptions == {}
    assert box.owned_parcels == []
    assert box.is_configured is False


async def test_saving_marks_the_box_configured(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "configured@example.com")
    assert (await read_buy_box(db_session, user_id)).is_configured is False

    saved = await write_buy_box(db_session, user_id, BuyBoxWrite(max_bid=1000))

    assert saved.is_configured is True
    assert (await read_buy_box(db_session, user_id)).is_configured is True


async def test_writing_twice_keeps_one_row_per_user(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "once@example.com")

    await write_buy_box(db_session, user_id, BuyBoxWrite(max_bid=50_000))
    await write_buy_box(db_session, user_id, BuyBoxWrite(max_bid=75_000))

    rows = await db_session.scalar(
        text("SELECT count(*) FROM buy_box WHERE user_id = :u"), {"u": user_id}
    )
    assert rows == 1
    reread = await read_buy_box(db_session, user_id)
    assert reread.max_bid == 75_000.0
    assert isinstance(reread.max_bid, float)


async def test_a_saved_box_round_trips_every_field(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "round@example.com")
    written = BuyBoxWrite(
        areas=[BuyBoxArea(name="Brewerytown", zip_codes=["19121"])],
        max_bid=42_000,
        target_use="flip",
        min_lot_sqft=900,
        zoning_codes=[" rsa-5 ", "cmx-2"],
        exclude_city_neighbor=True,
        exclude_open_violations=True,
        exclude_historic=False,
        exclude_flood=False,
        assumptions={"target_margin": 0.3},
        owned_parcels=["PHL:123", "phl:123", " phl:456 "],
    )

    saved = await write_buy_box(db_session, user_id, written)
    reread = await read_buy_box(db_session, user_id)

    assert saved == reread
    assert reread.areas[0].name == "Brewerytown"
    assert reread.target_use == "flip"
    assert reread.zoning_codes == ["RSA-5", "CMX-2"]
    assert reread.exclude_historic is False
    assert reread.owned_parcels == ["phl:123", "phl:456"]


async def test_an_unknown_assumption_name_is_refused() -> None:
    with pytest.raises(ValueError, match="Unknown deal assumptions: made_up_cost"):
        BuyBoxWrite(assumptions={"made_up_cost": 1.0})


async def test_a_fraction_assumption_outside_zero_to_one_is_refused() -> None:
    with pytest.raises(ValueError, match="target_margin must be a fraction"):
        BuyBoxWrite(assumptions={"target_margin": 1.4})


async def test_assumptions_are_read_per_user_and_empty_for_anonymous(
    db_session: AsyncSession,
) -> None:
    mine = await _user(db_session, "mine@example.com")
    theirs = await _user(db_session, "theirs@example.com")
    await write_buy_box(db_session, mine, BuyBoxWrite(assumptions={"soft_cost_pct": 0.11}))

    assert await buy_box_assumptions(db_session, mine) == {"soft_cost_pct": 0.11}
    assert await buy_box_assumptions(db_session, theirs) == {}
    assert await buy_box_assumptions(db_session, None) == {}


async def test_seeding_owned_parcels_matches_the_opa_owner_and_carries_provenance(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "seed@example.com")
    for parcel, owner in (
        ("phl:seed1", "ACME HOLDINGS LLC"),
        ("phl:seed2", "Acme  Holdings, L.L.C."),
        ("phl:seed3", "SOMEONE ELSE"),
    ):
        await db_session.execute(
            text(
                "INSERT INTO parcel (parcel_number, market_code, owner, is_vacant) "
                "VALUES (:p, 'phl', :o, true)"
            ),
            {"p": parcel, "o": owner},
        )
    await db_session.flush()

    result = await seed_owned_parcels(db_session, user_id, "acme holdings llc")

    assert result.added == ["phl:seed1", "phl:seed2"]
    assert result.owned_parcels == ["phl:seed1", "phl:seed2"]
    assert result.source == OWNER_SOURCE
    assert result.source_url.startswith("https://")
    assert result.fetched_at is not None


async def test_seeding_twice_adds_nothing_the_second_time(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "twice@example.com")
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, owner, is_vacant) "
            "VALUES ('phl:twice1', 'phl', 'REPEAT LLC', true)"
        )
    )
    await db_session.flush()

    first = await seed_owned_parcels(db_session, user_id, "REPEAT LLC")
    second = await seed_owned_parcels(db_session, user_id, "REPEAT LLC")

    assert first.added == ["phl:twice1"]
    assert second.added == []
    assert second.owned_parcels == ["phl:twice1"]


async def test_the_seed_key_matches_the_parcel_tables_own_owner_key(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "keymatch@example.com")
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, owner, is_vacant) "
            "VALUES ('phl:key1', 'phl', '  J. P.  Morgan,  Trust  ', true)"
        )
    )
    await db_session.flush()

    result = await seed_owned_parcels(db_session, user_id, "j p morgan trust")

    assert result.added == ["phl:key1"]


async def test_seeding_needs_an_owner_name(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "blank@example.com")

    with pytest.raises(ValidationError):
        await seed_owned_parcels(db_session, user_id, "   ")
