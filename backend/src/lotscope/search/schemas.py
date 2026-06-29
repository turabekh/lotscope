from typing import Any

from pydantic import BaseModel, Field, model_validator


class ParcelSearchResult(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    score: float


class ParcelSearchResponse(BaseModel):
    query: str
    results: list[ParcelSearchResult]


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class AreaSearchRequest(BaseModel):
    center: GeoPoint | None = None
    radius_m: float | None = Field(default=None, gt=0)
    polygon: dict[str, Any] | None = None
    vacant_only: bool = False
    zoning_codes: list[str] = Field(default_factory=list, max_length=40)
    limit: int = Field(default=200, ge=1, le=500)

    @model_validator(mode="after")
    def _exactly_one_shape(self) -> "AreaSearchRequest":
        has_radius = self.center is not None and self.radius_m is not None
        has_polygon = self.polygon is not None
        if has_radius == has_polygon:
            raise ValueError("Provide either center+radius_m or polygon, but not both.")
        return self


class SpatialParcelResult(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None
    lng: float | None
    lat: float | None
    distance_m: float | None = None


class AreaSearchResponse(BaseModel):
    count: int
    truncated: bool
    results: list[SpatialParcelResult]
