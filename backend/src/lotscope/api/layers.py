from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lotscope.api.deps import get_app_settings
from lotscope.core.config import Settings
from lotscope.tiles.layers import (
    PARCELS_FUNCTION,
    PARCELS_LAYER,
    VACANT_LOTS_FUNCTION,
    VACANT_LOTS_LAYER,
)

router = APIRouter(tags=["layers"])


class LayerInfo(BaseModel):
    name: str
    source_layer: str
    tile_url: str
    fields: list[str]


class LayersResponse(BaseModel):
    layers: list[LayerInfo]


def _tile_url(base_url: str, function: str) -> str:
    return f"{base_url.rstrip('/')}/{function}/{{z}}/{{x}}/{{y}}"


@router.get("/layers", response_model=LayersResponse)
async def layers(settings: Annotated[Settings, Depends(get_app_settings)]) -> LayersResponse:
    return LayersResponse(
        layers=[
            LayerInfo(
                name=PARCELS_LAYER,
                source_layer=PARCELS_LAYER,
                tile_url=_tile_url(settings.martin_url, PARCELS_FUNCTION),
                fields=["parcel_number", "address", "is_vacant", "base_zoning_code"],
            ),
            LayerInfo(
                name=VACANT_LOTS_LAYER,
                source_layer=VACANT_LOTS_LAYER,
                tile_url=_tile_url(settings.martin_url, VACANT_LOTS_FUNCTION),
                fields=["parcel_number", "address", "vacancy_confidence", "base_zoning_code"],
            ),
        ]
    )
