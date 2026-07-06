from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChecklistStatus = Literal["pass", "warn", "fail", "info"]
ChecklistAvailability = Literal["available", "no_data_source", "pending_load"]


class ChecklistItem(BaseModel):
    code: str
    category: str
    status: ChecklistStatus
    detail: str
    source: str | None = None
    availability: ChecklistAvailability = "available"


class ChecklistSummary(BaseModel):
    passed: int
    warnings: int
    failures: int
    info: int
    ready: bool


class ParcelChecklist(BaseModel):
    parcel_number: str
    items: list[ChecklistItem]
    summary: ChecklistSummary
    computed_at: datetime
