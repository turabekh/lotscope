"""What the Analyst is allowed to spend, and who is exempt from which ceiling."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.budget.pricing import usd_estimate
from lotscope.budget.service import (
    CHAT_SOURCE,
    JOB_SOURCE,
    check_analyst_budget,
    day_spend,
    record_analyst_usage,
    today,
)
from lotscope.core.config import Settings

pytestmark = pytest.mark.integration

MODEL = "claude-sonnet-5"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "analyst_daily_usd_per_user": 3.0,
        "analyst_daily_runs_per_user": 40,
        "analyst_daily_usd_global": 50.0,
        "analyst_model": MODEL,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def _user(session: AsyncSession, email: str, **columns: object) -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'pro', true)"
        ),
        {"e": email},
    )
    user_id = int(
        await session.scalar(text("SELECT id FROM app_user WHERE email = :e"), {"e": email})
    )
    user = await session.get(User, user_id)
    assert user is not None
    for key, value in columns.items():
        setattr(user, key, value)
    await session.flush()
    return user


async def _spend(session: AsyncSession, user: User, usd: str, *, source: str = CHAT_SOURCE) -> None:
    """Put an exact dollar figure on the ledger without guessing at token counts."""
    await session.execute(
        text(
            "INSERT INTO analyst_usage (user_id, day, source, input_tokens, output_tokens, "
            "usd_estimate, runs) VALUES (:u, :d, :s, 0, 0, :v, 1) "
            "ON CONFLICT (user_id, day, source) DO UPDATE SET "
            "usd_estimate = analyst_usage.usd_estimate + EXCLUDED.usd_estimate, "
            "runs = analyst_usage.runs + 1"
        ),
        {"u": user.id, "d": today(), "s": source, "v": Decimal(usd)},
    )
    await session.flush()


async def test_a_buyer_under_the_ceiling_may_run(db_session: AsyncSession) -> None:
    user = await _user(db_session, "under@example.com")
    await _spend(db_session, user, "1.50")

    verdict = await check_analyst_budget(db_session, user, _settings())

    assert verdict.allowed


async def test_the_dollar_ceiling_stops_the_next_run_and_says_why(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "spent@example.com")
    await _spend(db_session, user, "3.02")

    verdict = await check_analyst_budget(db_session, user, _settings())

    assert not verdict.allowed
    assert verdict.reason == "user_usd"
    assert "$3.02" in verdict.message
    assert "$3.00" in verdict.message
    assert "midnight UTC" in verdict.message


async def test_the_run_ceiling_stops_a_buyer_who_spent_almost_nothing(
    db_session: AsyncSession,
) -> None:
    """Forty cheap questions is still forty questions."""
    user = await _user(db_session, "chatty@example.com")
    await db_session.execute(
        text(
            "INSERT INTO analyst_usage (user_id, day, source, usd_estimate, runs) "
            "VALUES (:u, :d, 'chat', 0.02, 40)"
        ),
        {"u": user.id, "d": today()},
    )
    await db_session.flush()

    verdict = await check_analyst_budget(db_session, user, _settings())

    assert not verdict.allowed
    assert verdict.reason == "user_runs"
    assert "40 times today" in verdict.message


async def test_an_admin_can_raise_or_drop_one_account_without_a_deploy(
    db_session: AsyncSession,
) -> None:
    generous = await _user(db_session, "raised@example.com", analyst_daily_usd=Decimal("20.00"))
    stopped = await _user(db_session, "stopped@example.com", analyst_daily_usd=Decimal("0.00"))
    await _spend(db_session, generous, "9.00")

    assert (await check_analyst_budget(db_session, generous, _settings())).allowed
    verdict = await check_analyst_budget(db_session, stopped, _settings())
    assert not verdict.allowed
    assert verdict.reason == "user_usd"


async def test_a_comped_account_gets_the_same_ceiling_as_a_paying_one(
    db_session: AsyncSession,
) -> None:
    """Comp waives the price of a document, not the cost of the model."""
    comped = await _user(
        db_session,
        "comped@example.com",
        comp_until=datetime(2099, 1, 1, tzinfo=UTC),
    )
    await _spend(db_session, comped, "3.10")

    verdict = await check_analyst_budget(db_session, comped, _settings())

    assert not verdict.allowed
    assert verdict.reason == "user_usd"


async def test_the_nightly_brief_is_not_stopped_by_the_buyers_own_ceiling(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "briefed@example.com")
    await _spend(db_session, user, "9.99")

    chat = await check_analyst_budget(db_session, user, _settings())
    brief = await check_analyst_budget(db_session, user, _settings(), source=JOB_SOURCE)

    assert not chat.allowed
    assert brief.allowed


async def test_the_briefs_own_spend_does_not_count_against_the_buyers_ceiling(
    db_session: AsyncSession,
) -> None:
    """A brief the buyer did not ask for must never be why their next question is refused."""
    user = await _user(db_session, "nightly@example.com")
    await _spend(db_session, user, "40.00", source=JOB_SOURCE)

    assert (await check_analyst_budget(db_session, user, _settings())).allowed


async def test_a_long_run_is_stopped_partway_by_what_it_has_already_burned(
    db_session: AsyncSession,
) -> None:
    """The ceiling is checked with the tokens this run has spent but not yet recorded."""
    user = await _user(db_session, "midrun@example.com")
    await _spend(db_session, user, "2.90")

    verdict = await check_analyst_budget(
        db_session,
        user,
        _settings(),
        pending_input_tokens=40_000,
        pending_output_tokens=2_000,
        model=MODEL,
    )

    assert not verdict.allowed
    assert verdict.reason == "user_usd"


async def test_the_global_ceiling_refuses_everyone_including_the_brief(
    db_session: AsyncSession,
) -> None:
    heavy = await _user(db_session, "heavy@example.com")
    light = await _user(db_session, "light@example.com")
    await _spend(db_session, heavy, "50.00")

    chat = await check_analyst_budget(db_session, light, _settings())
    brief = await check_analyst_budget(db_session, light, _settings(), source=JOB_SOURCE)

    assert not chat.allowed
    assert chat.reason == "global_usd"
    assert "$50.00" in chat.message
    assert "platform limit" in chat.message
    # The global ceiling is the last line before the invoice, so nothing walks past it.
    assert not brief.allowed
    assert brief.reason == "global_usd"


async def test_recording_a_run_adds_to_the_day_rather_than_replacing_it(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "ledger@example.com")

    first = await record_analyst_usage(
        db_session, user_id=user.id, model=MODEL, input_tokens=10_000, output_tokens=1_000
    )
    second = await record_analyst_usage(
        db_session, user_id=user.id, model=MODEL, input_tokens=20_000, output_tokens=2_000
    )

    row = (
        await db_session.execute(
            text(
                "SELECT input_tokens, output_tokens, usd_estimate, runs FROM analyst_usage "
                "WHERE user_id = :u AND source = 'chat'"
            ),
            {"u": user.id},
        )
    ).one()
    assert row.input_tokens == 30_000
    assert row.output_tokens == 3_000
    assert row.runs == 2
    assert Decimal(row.usd_estimate) == first + second
    assert first == usd_estimate(MODEL, 10_000, 1_000)


async def test_the_spend_view_separates_what_is_metered_from_what_is_not(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "split@example.com")
    await _spend(db_session, user, "1.25", source=CHAT_SOURCE)
    await _spend(db_session, user, "4.00", source=JOB_SOURCE)

    spend = await day_spend(db_session, _settings())

    row = next(row for row in spend.users if row.user_id == user.id)
    assert row.chat_usd == Decimal("1.25")
    assert row.job_usd == Decimal("4.00")
    assert row.total_usd == Decimal("5.25")
    # The bill is the total; only the ceiling reads the chat half.
    assert spend.spend_usd >= Decimal("5.25")


async def test_an_unpriced_model_is_charged_at_the_dearest_rate_we_know() -> None:
    """An unpriced model must not be a hole in the ceiling."""
    assert usd_estimate("some-new-model", 1_000_000, 0) == usd_estimate(
        "claude-opus-5", 1_000_000, 0
    )
