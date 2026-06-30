from datetime import datetime
from typing import Any

from pydantic import BaseModel

from lotscope.assessment.analysis import AssessmentStatus, Confidence


class AssessmentResult(BaseModel):
    parcel_number: str
    status: AssessmentStatus
    assessed_market_value: float | None
    market_estimate: float | None
    market_low: float | None
    market_high: float | None
    gap: float | None
    gap_pct: float | None
    over_assessed_amount: float | None
    estimated_annual_tax_savings: float | None
    tax_rate: float
    confidence: Confidence
    reasons: list[str]
    disclaimer: str
    sources: list[dict[str, Any]]
    computed_at: datetime
