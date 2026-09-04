from unittest import mock

import httpx
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from lotscope.api.app import create_app
from lotscope.api.deps import get_redis, get_session
from lotscope.core.config import Settings, get_settings
from lotscope.ops.service import StaleDataset


def _with_email(app: FastAPI) -> None:
    settings = Settings(_env_file=None, smtp_host="smtp.example.test")
    app.dependency_overrides[get_settings] = lambda: settings


class _StubSession:
    async def execute(self, *_args: object, **_kwargs: object) -> object:
        return object()


class _StubRedis:
    async def ping(self) -> bool:
        return True


async def test_liveness_returns_ok() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "unknown"


async def test_readiness_reports_degraded_when_daily_ingestion_has_gone_stale() -> None:
    app = create_app()
    session = _StubSession()
    stale = [StaleDataset("phl", "opa_properties_public", "Stale — last success 49 days ago.")]

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_redis] = lambda: _StubRedis()
    _with_email(app)
    with mock.patch("lotscope.api.health.stale_automated_datasets", return_value=stale):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] is True
    assert body["redis"] is True
    assert body["ingestion"] is False
    assert "opa_properties_public" in body["stale_datasets"][0]


async def test_readiness_is_ready_when_ingestion_is_current() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _StubSession()
    app.dependency_overrides[get_redis] = lambda: _StubRedis()
    _with_email(app)
    with mock.patch("lotscope.api.health.stale_automated_datasets", return_value=[]):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    body = response.json()
    assert body["status"] == "ready"
    assert body["ingestion"] is True
    assert body["email"] is True
    assert body["email_allowlist_active"] is False
    assert body["stale_datasets"] == []


async def test_readiness_is_degraded_when_no_email_transport_is_configured() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _StubSession()
    app.dependency_overrides[get_redis] = lambda: _StubRedis()
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, smtp_host="")
    with mock.patch("lotscope.api.health.stale_automated_datasets", return_value=[]):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["email"] is False
    assert body["ingestion"] is True


async def test_readiness_does_not_call_unreadable_ingestion_healthy() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _StubSession()
    app.dependency_overrides[get_redis] = lambda: _StubRedis()
    _with_email(app)
    with mock.patch(
        "lotscope.api.health.stale_automated_datasets",
        side_effect=SQLAlchemyError("connection reset"),
    ):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    body = response.json()
    assert body["status"] == "degraded"
    assert body["ingestion"] is False
    assert "unknown" in body["stale_datasets"][0]


async def test_readiness_says_when_an_allowlist_is_still_gating_recipients() -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _StubSession()
    app.dependency_overrides[get_redis] = lambda: _StubRedis()
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        smtp_host="smtp.example.test",
        email_allowlist=["owner@parcelphl.online"],
    )
    with mock.patch("lotscope.api.health.stale_automated_datasets", return_value=[]):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")

    body = response.json()
    assert body["email"] is True
    assert body["email_allowlist_active"] is True
