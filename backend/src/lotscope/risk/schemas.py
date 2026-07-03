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
    max_allowable_offer: float | None
    bid_gap: float | None
    opportunity_score: int | None


class SheriffSaleCalendar(BaseModel):
    total: int
    returned: int
    items: list[SheriffSaleItem]


class RiskFlagSchema(BaseModel):
    code: str
    severity: Literal["high", "medium", "low", "info"]
    label: str
    detail: str
    source: str


class RiskResult(BaseModel):
    parcel_number: str
    risk_score: float
    flags: list[RiskFlagSchema]
    summary: str
    confidence: Literal["high", "medium", "low"]
    sources: list[dict[str, Any]]
    computed_at: datetime
