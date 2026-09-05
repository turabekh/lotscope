from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class CompResult(BaseModel):
    parcel_number: str
    address: str | None
    distance_ft: float
    sale_price: float
    sale_date: date | None
    lot_area_sqft: float | None
    price_per_sqft: float | None


class ValuationResult(BaseModel):
    parcel_number: str
    estimate: float | None
    low: float | None
    high: float | None
    price_per_sqft: float | None
    confidence: Literal["high", "medium", "low"]
    comp_count: int
    coefficient_of_variation: float | None
    comps: list[CompResult]
    reasons: list[str]
    wide_area: bool = False
    sources: list[dict[str, Any]]
    computed_at: datetime


class SheriffClearingEstimate(BaseModel):
    parcel_number: str
    zoning_class: str | None
    sufficient: bool
    estimate: float | None = None
    sample_size: int
    low: float | None = None
    high: float | None = None
    radius_m: float
    months: int
    minimum_sample: int
    reason: str | None = None
    source: str
    source_url: str
    computed_at: datetime
