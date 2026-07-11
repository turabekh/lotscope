from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI

from lotscope.api.app import create_app
from lotscope.api.deps import get_current_user, get_source_fetcher


def _admin_app(*, role: str = "admin") -> FastAPI:
    app = create_app()

    def _user() -> Any:
        return SimpleNamespace(id=1, role=role)

    app.dependency_overrides[get_current_user] = _user
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_fetch_sources_lists_known() -> None:
    app = _admin_app()
    async with _client(app) as client:
        resp = await client.get("/admin/fetch/sources")
    assert resp.status_code == 200
    labels = [source["label"] for source in resp.json()]
    assert "Dauphin repository list (PDF)" in labels


async def test_fetch_streams_bytes_as_attachment() -> None:
    app = _admin_app()

    async def _fetcher(url: str) -> bytes:
        assert url == "https://example.test/data/list.csv"
        return b"col1,col2\n1,2\n"

    app.dependency_overrides[get_source_fetcher] = lambda: _fetcher
    async with _client(app) as client:
        resp = await client.get(
            "/admin/fetch", params={"url": "https://example.test/data/list.csv"}
        )
    assert resp.status_code == 200
    assert resp.content == b"col1,col2\n1,2\n"
    assert 'filename="list.csv"' in resp.headers["content-disposition"]


async def test_fetch_rejects_non_http_url() -> None:
    app = _admin_app()
    app.dependency_overrides[get_source_fetcher] = lambda: lambda url: None
    async with _client(app) as client:
        resp = await client.get("/admin/fetch", params={"url": "file:///etc/passwd"})
    assert resp.status_code == 422


async def test_fetch_requires_admin() -> None:
    app = _admin_app(role="user")
    async with _client(app) as client:
        sources = await client.get("/admin/fetch/sources")
        fetch = await client.get("/admin/fetch", params={"url": "https://example.test/x"})
    assert sources.status_code == 403
    assert fetch.status_code == 403
