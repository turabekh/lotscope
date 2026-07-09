from typing import Any

from pydantic import BaseModel, ConfigDict


class MarketInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    state: str | None
    url_slug: str
    map_center: list[float]
    map_bounds: list[Any] | None
    default_zoom: float
    launch_status: str
    coverage_note: str | None
    hidden_surfaces: list[str] = []
    risk_coverage_note: str | None = None
    forced_sale_surface_label: str = "Sheriff sales"
