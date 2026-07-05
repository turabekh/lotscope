from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VarianceOutlook(BaseModel):
    parcel_number: str
    district: str | None
    population_label: str
    window_months: int
    decided: int
    granted: int
    grant_rate: float | None
    local_scope: str | None
    local_decided: int | None
    local_grant_rate: float | None
    reason: str | None
    sources: list[dict[str, Any]]
    computed_at: datetime
