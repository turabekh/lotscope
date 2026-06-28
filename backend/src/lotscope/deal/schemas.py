from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class DealAssumptionsSchema(BaseModel):
    construction_cost_per_sqft: float
    soft_cost_pct: float
    selling_cost_pct: float
    target_margin: float
    default_unit_sqft: float


class DealResult(BaseModel):
    parcel_number: str
    units: int | None
    arv: float | None
    per_unit_value: float | None
    gross_floor_area_sqft: float | None
    acquisition_cost: float | None
    construction_cost: float | None
    soft_cost: float | None
    selling_cost: float | None
    total_cost: float | None
    profit: float | None
    margin: float | None
    roi: float | None
    max_allowable_offer: float | None
    is_underpriced: bool | None
    deal_score: float | None
    comp_count: int
    confidence: Literal["high", "medium", "low"]
    assumptions: DealAssumptionsSchema
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime
