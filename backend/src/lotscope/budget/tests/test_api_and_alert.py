"""The refusal a buyer meets at the door, and the one email that says the day is nearly gone."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.app import create_app
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.budget.service import day_spend, maybe_alert_global_budget, today
from lotscope.core.config import Settings

pytestmark = pytest.mark.integration


class _Outbox:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "anthropic_api_key": "test-key",
        "analyst_daily_usd_per_user": 3.0,
        "analyst_daily_runs_per_user": 40,
        "analyst_daily_usd_global": 50.0,
        "analyst_model": "claude-sonnet-5",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def _user(session: AsyncSession, email: str, role: str = "user") -> User:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', :r, 'pro', true)"
        ),
        {"e": email, "r": role},
    )
    user_id = int(
        await session.scalar(text("SELECT id FROM app_user WHERE email = :e"), {"e": email})
    )
    user = await session.get(User, user_id)
    assert user is not None
    return user


async def _spend(session: AsyncSession, user: User, usd: str, source: str = "chat") -> None:
    await session.execute(
        text(
            "INSERT INTO analyst_usage (user_id, day, source, usd_estimate, runs) "
            "VALUES (:u, :d, :s, :v, 1) ON CONFLICT (user_id, day, source) DO UPDATE SET "
            "usd_estimate = analyst_usage.usd_estimate + EXCLUDED.usd_estimate"
        ),
        {"u": user.id, "d": today(), "s": source, "v": Decimal(usd)},
    )
    await session.flush()


def _app(db_session: AsyncSession, user: User, settings: Settings) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_app_settings] = lambda: settings
    return app


async def _post(app: FastAPI, body: dict[str, Any]) -> Any:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post("/analyst/messages", json=body)


async def test_a_buyer_over_the_ceiling_gets_429_and_the_same_sentence(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "door@example.com")
    await _spend(db_session, user, "3.40")

    response = await _post(_app(db_session, user, _settings()), {"text": "screen the sale"})

    assert response.status_code == 429
    detail = response.json()["detail"]
    assert "$3.40" in detail
    assert "$3.00" in detail
    assert "midnight UTC" in detail


async def test_a_buyer_under_the_ceiling_is_let_through(db_session: AsyncSession) -> None:
    user = await _user(db_session, "letin@example.com")
    await _spend(db_session, user, "0.10")

    response = await _post(_app(db_session, user, _settings()), {"text": "screen the sale"})

    assert response.status_code == 202
    assert response.json()["status"] == "running"


async def test_the_global_ceiling_refuses_a_buyer_who_has_spent_nothing(
    db_session: AsyncSession,
) -> None:
    heavy = await _user(db_session, "burner@example.com")
    innocent = await _user(db_session, "innocent@example.com")
    await _spend(db_session, heavy, "50.00")

    response = await _post(_app(db_session, innocent, _settings()), {"text": "hello"})

    assert response.status_code == 429
    assert "platform limit" in response.json()["detail"]


async def test_crossing_eighty_percent_emails_the_admins_once_a_day(
    db_session: AsyncSession,
) -> None:
    admin = await _user(db_session, "boss@example.com", role="admin")
    spender = await _user(db_session, "spender@example.com")
    await _spend(db_session, spender, "41.00")
    settings = _settings()
    outbox = _Outbox()

    first = await maybe_alert_global_budget(db_session, outbox, settings)
    # A second run crosses the same line. Same event, so no second email.
    await _spend(db_session, spender, "2.00")
    second = await maybe_alert_global_budget(db_session, outbox, settings)

    assert first == 1
    assert second == 0
    assert len(outbox.sent) == 1
    assert outbox.sent[0]["to"] == admin.email
    assert "82%" in outbox.sent[0]["subject"]
    assert "spender@example.com" in outbox.sent[0]["text"]


async def test_no_email_goes_out_below_the_warning_line(db_session: AsyncSession) -> None:
    await _user(db_session, "quiet-admin@example.com", role="admin")
    spender = await _user(db_session, "quiet@example.com")
    await _spend(db_session, spender, "39.00")
    outbox = _Outbox()

    assert await maybe_alert_global_budget(db_session, outbox, _settings()) == 0
    assert outbox.sent == []


async def test_yesterdays_alert_does_not_silence_todays(db_session: AsyncSession) -> None:
    await _user(db_session, "day-admin@example.com", role="admin")
    spender = await _user(db_session, "twoday@example.com")
    await _spend(db_session, spender, "45.00")
    settings = _settings()
    outbox = _Outbox()

    await maybe_alert_global_budget(
        db_session, outbox, settings, now=datetime.now(UTC).replace(hour=12)
    )
    tomorrow = datetime.now(UTC).replace(hour=12) + timedelta(days=1)
    # Same ledger, next day: the state row must not hold the alarm shut for ever.
    await db_session.execute(
        text("UPDATE analyst_usage SET day = :d WHERE user_id = :u"),
        {"d": tomorrow.date(), "u": spender.id},
    )
    await db_session.flush()
    again = await maybe_alert_global_budget(db_session, outbox, settings, now=tomorrow)

    assert again == 1
    assert len(outbox.sent) == 2


async def test_the_spend_view_reads_the_same_numbers_the_ceiling_does(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "view@example.com")
    await _spend(db_session, user, "2.00")
    await _spend(db_session, user, "6.00", source="job")

    spend = await day_spend(db_session, _settings())

    assert spend.spend_usd == Decimal("8.00")
    assert round(spend.fraction, 3) == 0.16
