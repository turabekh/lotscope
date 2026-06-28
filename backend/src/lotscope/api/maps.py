from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lotscope.api.deps import get_app_settings
from lotscope.core.config import Settings
from lotscope.tiles.google import MapType, create_basemap_session

router = APIRouter(prefix="/maps", tags=["maps"])

SettingsDep = Annotated[Settings, Depends(get_app_settings)]


class BasemapSessionResponse(BaseModel):
    map_type: str
    tile_url: str
    attribution: str
    tile_size: int


@router.get("/basemap-session", response_model=BasemapSessionResponse)
async def basemap_session(
    settings: SettingsDep, map_type: MapType = "satellite"
) -> BasemapSessionResponse:
    session = await create_basemap_session(settings, map_type)
    return BasemapSessionResponse(
        map_type=session.map_type,
        tile_url=session.tile_url,
        attribution=session.attribution,
        tile_size=session.tile_size,
    )
