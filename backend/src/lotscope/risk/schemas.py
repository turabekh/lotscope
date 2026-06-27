from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


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
