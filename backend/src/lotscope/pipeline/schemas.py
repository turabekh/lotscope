from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

Stage = Literal["lead", "diligence", "offer", "under_contract", "closed", "lost"]

STAGES: tuple[Stage, ...] = ("lead", "diligence", "offer", "under_contract", "closed", "lost")


class DealCreate(BaseModel):
    parcel_number: str = Field(min_length=1, max_length=40)
    stage: Stage = "lead"
    note: str | None = Field(default=None, max_length=2000)
    target_price: float | None = Field(default=None, ge=0)


class DealUpdate(BaseModel):
    stage: Stage | None = None
    note: str | None = Field(default=None, max_length=2000)
    target_price: float | None = Field(default=None, ge=0)
    next_action: str | None = Field(default=None, max_length=2000)
    next_action_due: date | None = None
    contact_name: str | None = Field(default=None, max_length=160)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_email: str | None = Field(default=None, max_length=255)


class DealItem(BaseModel):
    id: int
    parcel_number: str
    stage: Stage
    note: str | None
    target_price: float | None
    next_action: str | None
    next_action_due: date | None
    stage_entered_at: datetime | None
    contact_name: str | None
    contact_phone: str | None
    contact_email: str | None
    address: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None
    max_allowable_offer: float | None
    arv: float | None
    est_profit: float | None
    est_margin: float | None
    is_underpriced: bool | None
    updated_at: datetime


class DealActivityItem(BaseModel):
    id: int
    kind: str
    from_stage: str | None
    to_stage: str | None
    body: str | None
    created_at: datetime


class PipelineResponse(BaseModel):
    limit: int | None
    used: int
    deals: list[DealItem]


class TodayResponse(BaseModel):
    deals: list[DealItem]
