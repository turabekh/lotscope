from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

ResolutionMethod = Literal["spatial", "opa_attribute"]


class DistrictResolution(BaseModel):
    code: str
    method: ResolutionMethod


class BuildabilityResult(BaseModel):
    parcel_number: str
    district_code: str | None
    district_method: ResolutionMethod | None
    cited_section: str | None
    conforming: bool | None
    can_build_by_right: bool
    needs_variance: bool | None
    by_right_units: int | None
    max_height_ft: float | None
    buildable_area_sqft: float | None
    buildability_score: float
    confidence: Literal["high", "medium", "low"]
    requires_master_plan: bool = False
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime
