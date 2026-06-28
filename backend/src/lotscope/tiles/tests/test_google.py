from typing import cast

import httpx
import pytest
from redis.asyncio import Redis

from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, UpstreamError
from lotscope.tiles.google import (
    build_tile_url,
    create_basemap_session,
    fetch_viewport_attribution,
    resolve_basemap_session,
)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None, "google_maps_api_key": "test-key"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ok_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "createSession" in str(request.url)
        return httpx.Response(200, json={"session": "sess123"})

    return httpx.MockTransport(handler)


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.store[key] = value


def _redis() -> Redis:
    return cast(Redis, _FakeRedis())


class _CountingTransport(httpx.MockTransport):
    def __init__(self, *, expiry: int) -> None:
        self.session_calls = 0
        self.viewport_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            if "createSession" in str(request.url):
                self.session_calls += 1
                return httpx.Response(
                    200, json={"session": "sess123", "expiry": str(expiry), "tileWidth": 256}
                )
            self.viewport_calls += 1
            return httpx.Response(200, json={"copyright": "Imagery ©2026 Maxar, Google"})

        super().__init__(handler)


def test_build_tile_url() -> None:
    url = build_tile_url("https://tile.googleapis.com/v1", "S", "K")
    assert url == "https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?session=S&key=K"


async def test_create_session_embeds_session_and_key() -> None:
    session = await create_basemap_session(_settings(), "satellite", transport=_ok_transport())
    assert session.map_type == "satellite"
    assert "session=sess123" in session.tile_url
    assert "key=test-key" in session.tile_url
    assert session.tile_size == 256


async def test_missing_key_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        await create_basemap_session(Settings(_env_file=None), "satellite")


async def test_upstream_failure_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(UpstreamError):
        await create_basemap_session(_settings(), "roadmap", transport=httpx.MockTransport(handler))


async def test_malformed_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with pytest.raises(UpstreamError):
        await create_basemap_session(
            _settings(), "satellite", transport=httpx.MockTransport(handler)
        )


async def test_resolve_caches_session_token() -> None:
    redis = _redis()
    transport = _CountingTransport(expiry=2_000_000_000)

    first = await resolve_basemap_session(_settings(), redis, "satellite", transport=transport)
    second = await resolve_basemap_session(_settings(), redis, "satellite", transport=transport)

    assert "session=sess123" in first.tile_url
    assert second.tile_url == first.tile_url
    assert transport.session_calls == 1


async def test_expired_session_is_not_cached() -> None:
    redis = _redis()
    transport = _CountingTransport(expiry=1)

    await resolve_basemap_session(_settings(), redis, "satellite", transport=transport)
    await resolve_basemap_session(_settings(), redis, "satellite", transport=transport)

    assert transport.session_calls == 2


async def test_fetch_viewport_attribution_returns_copyright() -> None:
    redis = _redis()
    transport = _CountingTransport(expiry=2_000_000_000)

    text = await fetch_viewport_attribution(
        _settings(),
        redis,
        "satellite",
        zoom=15,
        north=40.0,
        south=39.9,
        east=-75.1,
        west=-75.2,
        transport=transport,
    )

    assert text == "Imagery ©2026 Maxar, Google"
    assert transport.viewport_calls == 1
