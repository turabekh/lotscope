from datetime import datetime
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


class DealItem(BaseModel):
    id: int
    parcel_number: str
    stage: Stage
    note: str | None
    target_price: float | None
    address: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None
    updated_at: datetime


class PipelineResponse(BaseModel):
    limit: int | None
    used: int
    deals: list[DealItem]
