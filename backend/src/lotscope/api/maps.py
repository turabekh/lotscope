from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from redis.asyncio import Redis

from lotscope.api.deps import get_app_settings, get_redis
from lotscope.core.config import Settings
from lotscope.tiles.google import (
    MapType,
    fetch_viewport_attribution,
    resolve_basemap_session,
)

router = APIRouter(prefix="/maps", tags=["maps"])

SettingsDep = Annotated[Settings, Depends(get_app_settings)]
RedisDep = Annotated[Redis, Depends(get_redis)]


class BasemapSessionResponse(BaseModel):
    map_type: str
    tile_url: str
    attribution: str
    tile_size: int


class AttributionResponse(BaseModel):
    attribution: str


@router.get("/basemap-session", response_model=BasemapSessionResponse)
async def basemap_session(
    settings: SettingsDep, redis: RedisDep, map_type: MapType = "satellite"
) -> BasemapSessionResponse:
    session = await resolve_basemap_session(settings, redis, map_type)
    return BasemapSessionResponse(
        map_type=session.map_type,
        tile_url=session.tile_url,
        attribution=session.attribution,
        tile_size=session.tile_size,
    )


@router.get("/attribution", response_model=AttributionResponse)
async def attribution(
    settings: SettingsDep,
    redis: RedisDep,
    north: Annotated[float, Query(ge=-90, le=90)],
    south: Annotated[float, Query(ge=-90, le=90)],
    east: Annotated[float, Query(ge=-180, le=180)],
    west: Annotated[float, Query(ge=-180, le=180)],
    zoom: Annotated[int, Query(ge=0, le=24)],
    map_type: MapType = "satellite",
) -> AttributionResponse:
    text = await fetch_viewport_attribution(
        settings,
        redis,
        map_type,
        zoom=zoom,
        north=north,
        south=south,
        east=east,
        west=west,
    )
    return AttributionResponse(attribution=text)
