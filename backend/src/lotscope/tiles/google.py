from dataclasses import dataclass
from typing import Literal

import httpx

from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, UpstreamError

MapType = Literal["satellite", "roadmap"]

_ATTRIBUTION = "Map data © Google"
_TILE_SIZE = 256


@dataclass(frozen=True)
class BasemapSession:
    map_type: MapType
    tile_url: str
    attribution: str
    tile_size: int


def build_tile_url(base_url: str, session: str, api_key: str) -> str:
    root = base_url.rstrip("/")
    return f"{root}/2dtiles/{{z}}/{{x}}/{{y}}?session={session}&key={api_key}"


async def create_basemap_session(
    settings: Settings,
    map_type: MapType,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BasemapSession:
    if not settings.google_maps_api_key:
        raise ConfigurationError("Google Maps is not configured.")
    root = settings.google_map_tiles_url.rstrip("/")
    url = f"{root}/createSession?key={settings.google_maps_api_key}"
    payload = {"mapType": map_type, "language": "en-US", "region": "US"}
    async with httpx.AsyncClient(
        transport=transport, timeout=settings.http_timeout_seconds
    ) as client:
        response = await client.post(url, json=payload)
    if response.status_code != httpx.codes.OK:
        raise UpstreamError("Google Map Tiles session request failed.")
    session = response.json().get("session")
    if not isinstance(session, str) or not session:
        raise UpstreamError("Google Map Tiles session response was malformed.")
    return BasemapSession(
        map_type=map_type,
        tile_url=build_tile_url(root, session, settings.google_maps_api_key),
        attribution=_ATTRIBUTION,
        tile_size=_TILE_SIZE,
    )
