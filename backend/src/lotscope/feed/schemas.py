from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FeedSummaryItem(BaseModel):
    code: str
    label: str
    count: int


class FeedEvent(BaseModel):
    parcel_number: str
    address: str | None
    code: str
    label: str
    severity: str
    detected_at: datetime
    old_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    opportunity_score: int | None


class FeedResponse(BaseModel):
    since: datetime
    total: int
    returned: int
    summary: list[FeedSummaryItem]
    events: list[FeedEvent]
