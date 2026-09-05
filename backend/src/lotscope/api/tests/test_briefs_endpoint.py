"""GET /briefs and GET /briefs/today."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.agent.signals import AnalystBrief, AnalystSignal
from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.config import Settings

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 5)


def _user(user_id: int) -> User:
    return User(
        id=user_id,
        email="brief-reader@example.com",
        hashed_password="x",
        full_name=None,
        role="user",
        tier="user",
        is_active=True,
        digest_frequency="weekly",
        created_at=datetime.now(UTC),
    )


def _app(session: AsyncSession, user_id: int) -> FastAPI:
    app = create_app()
    app.state.settings = Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_current_user] = lambda: _user(user_id)
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _make_user(session: AsyncSession, email: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
                "VALUES (:e, 'x', 'user', 'user', true) RETURNING id"
            ),
            {"e": email},
        )
    )


async def test_briefs_lists_newest_first_and_todays_carries_its_signals(
    db_session: AsyncSession,
) -> None:
    user_id = await _make_user(db_session, "briefs-api@example.com")
    for day, body in ((date(2026, 9, 4), "yesterday"), (TODAY, "today")):
        db_session.add(AnalystBrief(user_id=user_id, brief_date=day, text=body, signal_count=1))
    db_session.add(
        AnalystSignal(
            user_id=user_id,
            signal_key="sale_status:sheriff_sale_event:7",
            signal_date=TODAY,
            kind="sale_status",
            parcel_number="phl:191357500",
            headline="3862 Aspen St: status Active → Postponed",
            detail={},
            source="civilview",
            source_url="https://philadelphia.sheriffsale.com/",
            source_table="sheriff_sale_event",
            source_row_id="7",
        )
    )
    await db_session.flush()

    app = _app(db_session, user_id)
    async with _client(app) as client:
        listed = await client.get("/briefs")
        today = await client.get("/briefs/today")

    assert listed.status_code == 200
    assert [row["text"] for row in listed.json()] == ["today", "yesterday"]

    assert today.status_code == 200
    body = today.json()
    assert body["text"] == "today"
    assert [signal["headline"] for signal in body["signals"]] == [
        "3862 Aspen St: status Active → Postponed"
    ]
    assert body["signals"][0]["source"] == "civilview"


async def test_a_buyer_never_sees_another_buyers_brief(db_session: AsyncSession) -> None:
    mine = await _make_user(db_session, "brief-mine@example.com")
    theirs = await _make_user(db_session, "brief-theirs@example.com")
    db_session.add(AnalystBrief(user_id=theirs, brief_date=TODAY, text="not yours", signal_count=1))
    await db_session.flush()

    app = _app(db_session, mine)
    async with _client(app) as client:
        listed = await client.get("/briefs")
        today = await client.get("/briefs/today")

    assert listed.json() == []
    assert today.json() is None


async def test_a_quiet_day_returns_null_rather_than_an_error(db_session: AsyncSession) -> None:
    user_id = await _make_user(db_session, "brief-none@example.com")
    app = _app(db_session, user_id)
    async with _client(app) as client:
        response = await client.get("/briefs/today")

    assert response.status_code == 200
    assert response.json() is None
