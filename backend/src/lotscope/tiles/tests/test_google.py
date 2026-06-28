import httpx
import pytest

from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, UpstreamError
from lotscope.tiles.google import build_tile_url, create_basemap_session


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"_env_file": None, "google_maps_api_key": "test-key"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _ok_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "createSession" in str(request.url)
        return httpx.Response(200, json={"session": "sess123"})

    return httpx.MockTransport(handler)


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
