from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel


class SheriffSaleItem(BaseModel):
    parcel_number: str
    address: str | None
    case_number: str
    sale_type: str | None
    sale_date: date | None
    status: str | None
    opening_bid: float | None
    plaintiff: str | None
    is_vacant: bool | None
    base_zoning_code: str | None
    lot_area_sqft: float | None
    max_allowable_offer: float | None
    bid_gap: float | None
    opportunity_score: int | None


class SheriffSaleDate(BaseModel):
    sale_date: date
    listings: int
    vacant: int


class SheriffSaleDates(BaseModel):
    market: str
    dates: list[SheriffSaleDate]
    computed_at: datetime


class SheriffSaleCalendar(BaseModel):
    market: str
    label: str
    state: str
    note: str | None
    total: int
    returned: int
    items: list[SheriffSaleItem]


class NextSheriffSale(BaseModel):
    parcel_number: str
    case_number: str
    sale_type: str | None
    sale_date: date
    status: str | None
    opening_bid: float | None
    days_until: int


class RiskFlagSchema(BaseModel):
    code: str
    severity: Literal["high", "medium", "low", "info"]
    label: str
    detail: str
    source: str


class ViolationPosture(BaseModel):
    parcel_number: str
    violations_on_record: int
    open_violations: int


class RiskResult(BaseModel):
    parcel_number: str
    risk_score: float
    flags: list[RiskFlagSchema]
    summary: str
    confidence: Literal["high", "medium", "low"]
    sources: list[dict[str, Any]]
    computed_at: datetime
