from typing import Any

from pydantic import BaseModel, Field, model_validator

from lotscope.core.markets import Market


class ParcelSearchResult(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    score: float


class ParcelSearchResponse(BaseModel):
    query: str
    market: Market
    results: list[ParcelSearchResult]


class GeoPoint(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class AreaSearchRequest(BaseModel):
    center: GeoPoint | None = None
    radius_m: float | None = Field(default=None, gt=0)
    polygon: dict[str, Any] | None = None
    neighborhood: str | None = Field(default=None, min_length=1, max_length=120)
    vacant_only: bool = False
    zoning_codes: list[str] = Field(default_factory=list, max_length=40)
    min_lot_area_sqft: float | None = Field(default=None, ge=0)
    max_lot_area_sqft: float | None = Field(default=None, ge=0)
    min_market_value: float | None = Field(default=None, ge=0)
    max_market_value: float | None = Field(default=None, ge=0)
    min_opportunity_score: int | None = Field(default=None, ge=0, le=100)
    min_distress_score: int | None = Field(default=None, ge=0, le=100)
    delinquent_only: bool = False
    sheriff_sale_only: bool = False
    underpriced_only: bool = False
    by_right_only: bool = False
    limit: int = Field(default=200, ge=1, le=500)

    @model_validator(mode="after")
    def _exactly_one_shape(self) -> "AreaSearchRequest":
        shapes = [
            self.center is not None and self.radius_m is not None,
            self.polygon is not None,
            self.neighborhood is not None,
        ]
        if sum(shapes) != 1:
            raise ValueError("Provide exactly one of: center+radius_m, polygon, or neighborhood.")
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
    total: int
    truncated: bool
    results: list[SpatialParcelResult]
