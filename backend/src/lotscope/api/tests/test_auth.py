from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import get_app_settings, get_session
from lotscope.core.config import Settings

pytestmark = pytest.mark.integration


def _app(session: AsyncSession) -> FastAPI:
    app = create_app()

    async def _override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override_session
    app.dependency_overrides[get_app_settings] = lambda: Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_register_login_me_flow(db_session: AsyncSession) -> None:
    async with _client(_app(db_session)) as client:
        registered = await client.post(
            "/auth/register",
            json={"email": "u@example.com", "password": "hunter2-strong", "full_name": "U"},
        )
        logged_in = await client.post(
            "/auth/login", json={"email": "u@example.com", "password": "hunter2-strong"}
        )
        token = logged_in.json()["access_token"]
        me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        unauthenticated = await client.get("/auth/me")

    assert registered.status_code == 202
    assert registered.json() == {
        "email": "u@example.com",
        "verification_required": True,
        "detail": "Check your email for a confirmation link.",
    }
    assert logged_in.status_code == 200
    assert me.status_code == 200
    assert me.json()["email"] == "u@example.com"
    assert unauthenticated.status_code == 401


async def test_refresh_issues_a_new_token_for_valid_session(db_session: AsyncSession) -> None:
    async with _client(_app(db_session)) as client:
        await client.post(
            "/auth/register", json={"email": "r@example.com", "password": "hunter2-strong"}
        )
        logged_in = await client.post(
            "/auth/login", json={"email": "r@example.com", "password": "hunter2-strong"}
        )
        token = logged_in.json()["access_token"]
        refreshed = await client.post("/auth/refresh", headers={"Authorization": f"Bearer {token}"})
        unauthenticated = await client.post("/auth/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert unauthenticated.status_code == 401


async def test_login_rejects_bad_credentials(db_session: AsyncSession) -> None:
    async with _client(_app(db_session)) as client:
        await client.post(
            "/auth/register", json={"email": "v@example.com", "password": "hunter2-strong"}
        )
        bad = await client.post(
            "/auth/login", json={"email": "v@example.com", "password": "wrong-password"}
        )

    assert bad.status_code == 401
    assert bad.json()["error"] == "AuthError"


async def test_register_validates_email_and_password(db_session: AsyncSession) -> None:
    async with _client(_app(db_session)) as client:
        bad_email = await client.post(
            "/auth/register", json={"email": "not-an-email", "password": "hunter2-strong"}
        )
        short_password = await client.post(
            "/auth/register", json={"email": "ok@example.com", "password": "short"}
        )

    assert bad_email.status_code == 422
    assert short_password.status_code == 422
