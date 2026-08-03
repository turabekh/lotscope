from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from lotscope.zoning.confidence import Confidence

ChecklistStatus = Literal["pass", "fail", "potential_issue", "not_evaluated", "not_applicable"]
ChecklistAvailability = Literal["available", "no_data_source", "pending_load"]


class ChecklistItem(BaseModel):
    code: str
    label: str
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
    not_evaluated: int = 0
    ready: bool


class ParcelChecklist(BaseModel):
    parcel_number: str
    items: list[ChecklistItem]
    summary: ChecklistSummary
    buildability_confidence: Confidence | None = None
    buildability_confidence_reasons: list[str] = []
    computed_at: datetime
