import contextlib
import json
import time
from dataclasses import dataclass
from typing import Literal

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, UpstreamError

MapType = Literal["satellite", "roadmap"]

_REFUSED_MESSAGE = (
    "Google would not issue a basemap session for this key, so the satellite basemap is "
    "unavailable. The map falls back to the open raster basemap."
)
_ATTRIBUTION = "Map data © Google"
_TILE_SIZE = 256
_SESSION_CACHE_PREFIX = "gmaps:session"
_EXPIRY_BUFFER_SECONDS = 300
# How long to stop asking after Google refuses. A key it will not accept does not start
# working within the minute, and every map mount was spending a round trip finding out.
_REFUSAL_TTL_SECONDS = 600
_REFUSAL_CACHE_PREFIX = "gmaps:refused"


@dataclass(frozen=True)
class BasemapSession:
    map_type: MapType
    tile_url: str
    attribution: str
    tile_size: int


@dataclass(frozen=True)
class RawSession:
    token: str
    expiry_unix: int
    tile_size: int


def _require_key(settings: Settings) -> str:
    if not settings.google_maps_api_key:
        raise ConfigurationError("Google Maps is not configured.")
    return settings.google_maps_api_key


def build_tile_url(base_url: str, session: str, api_key: str) -> str:
    root = base_url.rstrip("/")
    return f"{root}/2dtiles/{{z}}/{{x}}/{{y}}?session={session}&key={api_key}"


def _build_session(
    settings: Settings, map_type: MapType, token: str, tile_size: int
) -> BasemapSession:
    root = settings.google_map_tiles_url.rstrip("/")
    return BasemapSession(
        map_type=map_type,
        tile_url=build_tile_url(root, token, _require_key(settings)),
        attribution=_ATTRIBUTION,
        tile_size=tile_size,
    )


async def request_session(
    settings: Settings,
    map_type: MapType,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> RawSession:
    api_key = _require_key(settings)
    root = settings.google_map_tiles_url.rstrip("/")
    url = f"{root}/createSession?key={api_key}"
    payload = {"mapType": map_type, "language": "en-US", "region": "US"}
    async with httpx.AsyncClient(
        transport=transport, timeout=settings.http_timeout_seconds
    ) as client:
        response = await client.post(url, json=payload)
    if response.status_code != httpx.codes.OK:
        raise UpstreamError("Google Map Tiles session request failed.")
    body = response.json()
    token = body.get("session")
    if not isinstance(token, str) or not token:
        raise UpstreamError("Google Map Tiles session response was malformed.")
    tile_size = body.get("tileWidth") if isinstance(body.get("tileWidth"), int) else _TILE_SIZE
    expiry = int(body["expiry"]) if str(body.get("expiry", "")).isdigit() else 0
    return RawSession(token=token, expiry_unix=expiry, tile_size=tile_size)


async def create_basemap_session(
    settings: Settings,
    map_type: MapType,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BasemapSession:
    raw = await request_session(settings, map_type, transport=transport)
    return _build_session(settings, map_type, raw.token, raw.tile_size)


async def _resolve_token(
    settings: Settings,
    redis: Redis,
    map_type: MapType,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[str, int]:
    cache_key = f"{_SESSION_CACHE_PREFIX}:{map_type}"
    cached: bytes | str | None = None
    with contextlib.suppress(RedisError):
        cached = await redis.get(cache_key)
    if cached is not None:
        data = json.loads(cached)
        return str(data["token"]), int(data["tile_size"])
    raw = await request_session(settings, map_type, transport=transport)
    ttl = raw.expiry_unix - int(time.time()) - _EXPIRY_BUFFER_SECONDS
    if ttl > 0:
        entry = json.dumps({"token": raw.token, "tile_size": raw.tile_size})
        with contextlib.suppress(RedisError):
            await redis.set(cache_key, entry, ex=ttl)
    return raw.token, raw.tile_size


async def resolve_basemap_session(
    settings: Settings,
    redis: Redis,
    map_type: MapType,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BasemapSession:
    """A Google basemap session, or a plain "not available" if Google will not give one.

    An unusable key is the same answer to the caller as no key at all — the map falls
    back to the raster basemap either way — so it is reported as unconfigured rather than
    as a 502 the client has to interpret. The refusal is remembered for ten minutes so a
    key Google rejects is not re-offered to it on every map mount.
    """
    _require_key(settings)
    refusal_key = f"{_REFUSAL_CACHE_PREFIX}:{map_type}"
    with contextlib.suppress(RedisError):
        if await redis.get(refusal_key) is not None:
            raise ConfigurationError(_REFUSED_MESSAGE)
    try:
        token, tile_size = await _resolve_token(settings, redis, map_type, transport=transport)
    except UpstreamError as error:
        with contextlib.suppress(RedisError):
            await redis.set(refusal_key, "1", ex=_REFUSAL_TTL_SECONDS)
        raise ConfigurationError(_REFUSED_MESSAGE) from error
    return _build_session(settings, map_type, token, tile_size)


async def fetch_viewport_attribution(
    settings: Settings,
    redis: Redis,
    map_type: MapType,
    *,
    zoom: int,
    north: float,
    south: float,
    east: float,
    west: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    api_key = _require_key(settings)
    token, _ = await _resolve_token(settings, redis, map_type, transport=transport)
    params: dict[str, str | int | float] = {
        "session": token,
        "key": api_key,
        "zoom": zoom,
        "north": north,
        "south": south,
        "east": east,
        "west": west,
    }
    async with httpx.AsyncClient(
        transport=transport, timeout=settings.http_timeout_seconds
    ) as client:
        response = await client.get(settings.google_viewport_url, params=params)
    if response.status_code != httpx.codes.OK:
        raise UpstreamError("Google Map Tiles viewport request failed.")
    copyright_text = response.json().get("copyright")
    return copyright_text if isinstance(copyright_text, str) and copyright_text else _ATTRIBUTION
