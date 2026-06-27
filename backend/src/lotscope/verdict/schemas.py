from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VerdictResult(BaseModel):
    parcel_number: str
    verdict_version: str
    buildability_score: float | None
    opportunity_score: float
    summary: str
    can_build_by_right: bool | None
    by_right_units: int | None
    max_height_ft: float | None
    needs_variance: bool | None
    buildable_area_sqft: float | None
    value_estimate_low: float | None
    value_estimate_high: float | None
    value_confidence: float | None
    assessment_market_gap: float | None
    risk_score: float | None
    risk_flags: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    computed_at: datetime
