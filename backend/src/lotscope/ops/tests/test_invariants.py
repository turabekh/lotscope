import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ops.invariants import INVARIANTS, Invariant, breaches, check_invariants

pytestmark = pytest.mark.integration


async def _parcel(session: AsyncSession, number: str) -> None:
    await session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES (:n, 'phl')"),
        {"n": number},
    )


async def _verdict(session: AsyncSession, number: str, **columns: object) -> None:
    columns.setdefault("verdict_version", "v10")
    keys = ", ".join(columns)
    binds = ", ".join(f":{key}" for key in columns)
    await session.execute(
        text(
            f"INSERT INTO parcel_verdict (parcel_number, computed_at, {keys}) "
            f"VALUES (:parcel_number, now(), {binds})"
        ),
        {"parcel_number": number, **columns},
    )


def _named(name: str) -> tuple[Invariant, ...]:
    return tuple(item for item in INVARIANTS if item.name == name)


async def test_a_clean_market_breaches_nothing(db_session: AsyncSession) -> None:
    await _parcel(db_session, "inv-clean")
    await _verdict(
        db_session,
        "inv-clean",
        recommendation="strong_candidate",
        est_profit=50000,
        est_margin=0.25,
        can_build_by_right=True,
        needs_variance=False,
    )
    await db_session.flush()

    assert breaches(await check_invariants(db_session, "phl")) == []


async def test_a_strong_candidate_losing_money_is_caught(db_session: AsyncSession) -> None:
    await _parcel(db_session, "inv-loss")
    await _verdict(db_session, "inv-loss", recommendation="strong_candidate", est_profit=-1000)
    await db_session.flush()

    results = await check_invariants(db_session, "phl", _named("strong_candidate_makes_money"))

    assert results[0].violations == 1
    assert results[0].breached is True


async def test_a_viable_margin_called_unattractive_is_caught(db_session: AsyncSession) -> None:
    await _parcel(db_session, "inv-contradiction")
    await _verdict(
        db_session,
        "inv-contradiction",
        recommendation="economics_unattractive",
        est_margin=0.13,
        est_profit=464878,
    )
    await db_session.flush()

    results = await check_invariants(
        db_session, "phl", _named("viable_margin_is_not_called_unattractive")
    )

    assert results[0].violations == 1


async def test_by_right_contradictions_are_caught(db_session: AsyncSession) -> None:
    await _parcel(db_session, "inv-byright")
    await _verdict(
        db_session,
        "inv-byright",
        can_build_by_right=True,
        needs_variance=True,
        recommendation="high_entitlement_risk",
    )
    await db_session.flush()

    variance = await check_invariants(
        db_session, "phl", _named("by_right_does_not_need_a_variance")
    )
    entitlement = await check_invariants(
        db_session, "phl", _named("by_right_is_not_entitlement_risk")
    )

    assert variance[0].violations == 1
    assert entitlement[0].violations == 1


async def test_a_wide_value_range_is_tolerated_until_it_dominates(
    db_session: AsyncSession,
) -> None:
    for index in range(9):
        await _parcel(db_session, f"inv-tight-{index}")
        await _verdict(
            db_session, f"inv-tight-{index}", value_estimate_low=100, value_estimate_high=200
        )
    await _parcel(db_session, "inv-wide-0")
    await _verdict(db_session, "inv-wide-0", value_estimate_low=100, value_estimate_high=5000)
    await db_session.flush()

    tolerated = await check_invariants(db_session, "phl", _named("value_range_stays_interpretable"))
    assert tolerated[0].breached is False

    for index in range(5):
        await _parcel(db_session, f"inv-wide-{index + 1}")
        await _verdict(
            db_session, f"inv-wide-{index + 1}", value_estimate_low=100, value_estimate_high=5000
        )
    await db_session.flush()

    breached = await check_invariants(db_session, "phl", _named("value_range_stays_interpretable"))
    assert breached[0].breached is True
