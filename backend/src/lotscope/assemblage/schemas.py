from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Acquirability = Literal["same_owner", "city_owned", "vacant", "built"]
Potential = Literal["high", "medium", "low", "none"]
UnitBasis = Literal["per_unit", "far_estimate", "flat_cap"]


class AdjacentLot(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    lot_area_sqft: float | None
    frontage_ft: float | None
    market_value: float | None
    is_vacant: bool | None
    is_city_owned: bool | None
    same_owner: bool
    same_zoning: bool
    shared_boundary_ft: float | None
    acquirability: Acquirability
    is_candidate: bool


class AssemblageSummary(BaseModel):
    adjacent_count: int
    candidate_count: int
    combined_lot_area_sqft: float | None
    combined_frontage_ft: float | None
    by_right_units_current: int | None
    by_right_units_combined: int | None
    units_basis: UnitBasis | None
    has_same_owner_neighbor: bool
    has_city_owned_neighbor: bool
    has_vacant_neighbor: bool


class AssemblageResult(BaseModel):
    parcel_number: str
    potential: Potential
    summary: AssemblageSummary
    neighbors: list[AdjacentLot]
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime
