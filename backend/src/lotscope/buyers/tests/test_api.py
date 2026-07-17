from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_redis, get_session

pytestmark = pytest.mark.integration


class _FailingRedis:
    async def incr(self, *args: Any, **kwargs: Any) -> int:
        raise RedisError("no redis in tests")

    async def expire(self, *args: Any, **kwargs: Any) -> bool:
        raise RedisError("no redis in tests")


def _app(db_session: AsyncSession, *, tier: str = "investor") -> FastAPI:
    app = create_app()

    async def _session() -> Any:
        yield db_session

    def _user() -> Any:
        return SimpleNamespace(id=1, role="user", tier=tier)

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_redis] = lambda: _FailingRedis()
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _seed_buyer(db_session: AsyncSession, market: str = "phl") -> None:
    await db_session.execute(
        text(
            "INSERT INTO buyer_profile (market_code, buyer_key, display_name, purchases_window, "
            "lot_purchases_window, activity_centroid, computed_at) VALUES "
            "(:m, 'THEDOOR LLC', 'THEDOOR LLC', 4, 4, ST_SetSRID(ST_MakePoint(5, 5), 2272), now())"
        ),
        {"m": market},
    )
    await db_session.flush()


async def test_roster_requires_investor_tier(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.get("/buyers")
    assert resp.status_code == 429


async def test_investor_sees_roster(db_session: AsyncSession) -> None:
    await _seed_buyer(db_session)
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert body["total"] == 1
    assert body["buyers"][0]["buyer_key"] == "THEDOOR LLC"


async def test_pgh_market_returns_unavailable_state(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers", params={"market": "pgh"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["buyers"] == []
    assert body["note"]


async def test_hbg_market_returns_unavailable_state(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers", params={"market": "hbg"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is False
    assert body["buyers"] == []
    assert body["note"]


@pytest.mark.parametrize(("slug", "code"), [("harrisburg", "hbg"), ("pittsburgh", "pgh")])
async def test_gated_markets_are_unavailable_when_called_by_url_slug(
    db_session: AsyncSession, slug: str, code: str
) -> None:
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers", params={"market": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["market_code"] == code
    assert body["available"] is False
    assert body["note"]


async def test_roster_by_url_slug_returns_the_same_buyers_as_the_market_code(
    db_session: AsyncSession,
) -> None:
    await _seed_buyer(db_session)
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        by_slug = await client.get("/buyers", params={"market": "philadelphia"})
        by_code = await client.get("/buyers", params={"market": "phl"})
    assert by_slug.status_code == 200
    assert by_slug.json() == by_code.json()
    assert by_slug.json()["total"] == 1


async def test_unknown_market_is_rejected(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers", params={"market": "atlantis"})
    assert resp.status_code == 422


async def test_export_requires_investor(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="pro")
    async with _client(app) as client:
        resp = await client.get("/buyers/export")
    assert resp.status_code == 429


async def test_export_returns_csv_for_investor(db_session: AsyncSession) -> None:
    await _seed_buyer(db_session)
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "THEDOOR LLC" in body
    assert "Fair Housing" in body


async def test_export_gated_market_is_empty_but_valid(db_session: AsyncSession) -> None:
    app = _app(db_session, tier="investor")
    async with _client(app) as client:
        resp = await client.get("/buyers/export", params={"market": "pgh"})
    assert resp.status_code == 200
    assert "Entity" in resp.text
    assert "Fair Housing" in resp.text
