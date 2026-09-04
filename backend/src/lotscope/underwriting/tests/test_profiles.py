import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ConflictError, NotFoundError
from lotscope.underwriting.schemas import BuyBox, ProfileWrite
from lotscope.underwriting.service import (
    create_profile,
    delete_profile,
    find_buy_box_matches,
    get_profile,
    list_profiles,
    update_profile,
)

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
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email = :e"), {"e": email}))


def _write(
    name: str = "My box",
    *,
    is_default: bool = False,
    assumptions: dict[str, float] | None = None,
) -> ProfileWrite:
    return ProfileWrite(
        name=name,
        is_default=is_default,
        assumptions=assumptions if assumptions is not None else {"target_margin": 0.25},
        buy_box=BuyBox(markets=["philadelphia"], min_units=1, max_units=4),
    )


async def test_a_profile_belongs_to_its_owner_and_is_invisible_to_others(
    db_session: AsyncSession,
) -> None:
    alice = await _user(db_session, "alice@example.com")
    bob = await _user(db_session, "bob@example.com")
    created = await create_profile(db_session, alice, _write())

    assert [p.id for p in await list_profiles(db_session, alice)] == [created.id]
    assert await list_profiles(db_session, bob) == []


async def test_another_user_cannot_read_a_profile(db_session: AsyncSession) -> None:
    alice = await _user(db_session, "alice@example.com")
    bob = await _user(db_session, "bob@example.com")
    created = await create_profile(db_session, alice, _write())

    with pytest.raises(NotFoundError):
        await get_profile(db_session, created.id, bob)


async def test_another_user_cannot_update_or_delete_a_profile(db_session: AsyncSession) -> None:
    alice = await _user(db_session, "alice@example.com")
    bob = await _user(db_session, "bob@example.com")
    created = await create_profile(db_session, alice, _write())

    with pytest.raises(NotFoundError):
        await update_profile(db_session, created.id, bob, _write(name="Hijacked"))
    with pytest.raises(NotFoundError):
        await delete_profile(db_session, created.id, bob)

    assert (await get_profile(db_session, created.id, alice)).name == "My box"


async def test_updating_a_profile_advances_its_version(db_session: AsyncSession) -> None:
    alice = await _user(db_session, "alice@example.com")
    created = await create_profile(db_session, alice, _write())
    assert created.version == 1

    updated = await update_profile(
        db_session, created.id, alice, _write(assumptions={"target_margin": 0.3})
    )
    assert updated.version == 2
    assert updated.assumptions["target_margin"] == 0.3


async def test_two_users_can_hold_differently_named_profiles_without_collision(
    db_session: AsyncSession,
) -> None:
    alice = await _user(db_session, "alice@example.com")
    bob = await _user(db_session, "bob@example.com")
    await create_profile(db_session, alice, _write(name="Rowhouse"))
    bobs = await create_profile(db_session, bob, _write(name="Rowhouse"))
    assert bobs.name == "Rowhouse"


async def test_a_user_cannot_reuse_one_of_their_own_profile_names(
    db_session: AsyncSession,
) -> None:
    alice = await _user(db_session, "alice@example.com")
    await create_profile(db_session, alice, _write(name="Rowhouse"))
    with pytest.raises(ConflictError):
        await create_profile(db_session, alice, _write(name="Rowhouse"))


async def test_only_one_profile_is_default_per_user(db_session: AsyncSession) -> None:
    alice = await _user(db_session, "alice@example.com")
    first = await create_profile(db_session, alice, _write(name="A", is_default=True))
    await create_profile(db_session, alice, _write(name="B", is_default=True))

    profiles = {p.name: p.is_default for p in await list_profiles(db_session, alice)}
    assert profiles == {"A": False, "B": True}
    assert first.id is not None


def test_a_percentage_assumption_outside_zero_to_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="fraction in"):
        ProfileWrite(name="bad", assumptions={"target_margin": 25.0})


def test_a_negative_assumption_is_rejected() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        ProfileWrite(name="bad", assumptions={"construction_cost_per_sqft": -5.0})


def test_a_blank_profile_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="needs a name"):
        ProfileWrite(name="   ")


async def _vacant_parcel_with_verdict(
    db_session: AsyncSession,
    parcel_number: str,
    *,
    mao: float | None,
    margin: float | None,
    units: int | None,
    risk: float | None,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, is_vacant) "
            "VALUES (:pn, 'phl', '1 Test St', true)"
        ),
        {"pn": parcel_number},
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_verdict (parcel_number, verdict_version, opportunity_score, "
            "max_allowable_offer, est_margin, by_right_units, risk_score) "
            "VALUES (:pn, 'v8', 70, :mao, :margin, :units, :risk)"
        ),
        {"pn": parcel_number, "mao": mao, "margin": margin, "units": units, "risk": risk},
    )
    await db_session.flush()


async def test_matches_without_a_default_profile_report_no_profile(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "nobox@x.co")
    result = await find_buy_box_matches(db_session, owner, market="phl", limit=10)
    assert result.has_profile is False
    assert result.total == 0
    assert result.matches == []


async def test_matches_apply_the_default_buy_box(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "box@x.co")
    await create_profile(
        db_session,
        owner,
        ProfileWrite(
            name="Box",
            is_default=True,
            assumptions={},
            buy_box=BuyBox(max_acquisition_price=150_000.0, min_margin=0.20),
        ),
    )
    await _vacant_parcel_with_verdict(
        db_session, "phl:match", mao=120_000.0, margin=0.30, units=3, risk=10.0
    )
    await _vacant_parcel_with_verdict(
        db_session, "phl:tooexpensive", mao=400_000.0, margin=0.30, units=3, risk=10.0
    )

    result = await find_buy_box_matches(db_session, owner, market="phl", limit=10)
    assert result.has_profile is True
    assert [m.parcel_number for m in result.matches] == ["phl:match"]
    assert result.criteria_applied == ["max_acquisition_price", "min_margin"]


async def test_unknown_values_never_match_a_stated_criterion(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "unknown@x.co")
    await create_profile(
        db_session,
        owner,
        ProfileWrite(
            name="Box",
            is_default=True,
            assumptions={},
            buy_box=BuyBox(max_acquisition_price=150_000.0, min_margin=0.20),
        ),
    )
    await _vacant_parcel_with_verdict(
        db_session, "phl:nomao", mao=None, margin=0.30, units=3, risk=10.0
    )
    await _vacant_parcel_with_verdict(
        db_session, "phl:nomargin", mao=100_000.0, margin=None, units=3, risk=10.0
    )

    result = await find_buy_box_matches(db_session, owner, market="phl", limit=10)
    assert result.total == 0
    assert result.matches == []
