from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SavedParcelCreate(BaseModel):
    parcel_number: str = Field(min_length=1, max_length=40)
    tags: list[str] = Field(default_factory=list, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class SavedParcelUpdate(BaseModel):
    tags: list[str] | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class WatchlistChange(BaseModel):
    code: str
    label: str
    severity: Literal["high", "medium", "info"]


class WatchlistItem(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None
    tags: list[str]
    note: str | None
    created_at: datetime
    changes: list[WatchlistChange] = Field(default_factory=list)
    has_alerts: bool = False


class WatchlistResponse(BaseModel):
    limit: int | None
    used: int
    alerts: int
    items: list[WatchlistItem]
