from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Tier = Literal["high", "medium", "low", "none"]


class DistressFactor(BaseModel):
    code: str
    label: str
    weight: int


class DistressResult(BaseModel):
    parcel_number: str
    score: int
    tier: Tier
    version: str
    factors: list[DistressFactor]
    sources: list[dict[str, Any]]
    computed_at: datetime


class LeadItem(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    total_due: float | None
    in_sheriff_sale: bool | None
    score: int
    top_factors: list[str]
    deal_score: float | None = None
    max_allowable_offer: float | None = None
    is_underpriced: bool | None = None


class LeadsResponse(BaseModel):
    tier: str
    limit: int
    returned: int
    leads: list[LeadItem]


class MailRecipient(BaseModel):
    parcel_number: str
    property_address: str | None
    owner: str
    mailing_address: str
