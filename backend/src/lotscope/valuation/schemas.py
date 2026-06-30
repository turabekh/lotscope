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
    sources: list[dict[str, Any]]
    computed_at: datetime
