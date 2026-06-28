from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ChecklistStatus = Literal["pass", "warn", "fail", "info"]


class ChecklistItem(BaseModel):
    code: str
    category: str
    status: ChecklistStatus
    detail: str
    source: str | None = None


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
