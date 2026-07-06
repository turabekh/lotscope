from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class DealAssumptionsSchema(BaseModel):
    construction_cost_per_sqft: float
    soft_cost_pct: float
    selling_cost_pct: float
    target_margin: float
    default_unit_sqft: float
    max_unit_sqft: float


class ScenarioItem(BaseModel):
    units: int
    by_right: bool
    arv: float | None
    total_cost: float | None
    profit: float | None
    margin: float | None
    roi: float | None
    max_allowable_offer: float | None
    deal_score: float | None
    infeasible: bool = False


class ScenariosResult(BaseModel):
    parcel_number: str
    by_right_units: int | None
    recommended_units: int | None
    scenarios: list[ScenarioItem]
    confidence: Literal["high", "medium", "low"]
    assumptions: DealAssumptionsSchema
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime


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
    infeasible: bool = False
    comp_count: int
    confidence: Literal["high", "medium", "low"]
    assumptions: DealAssumptionsSchema
    assumptions_source: Literal["market_default", "calibrated"] = "market_default"
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime
