from datetime import datetime
from typing import Any

from pydantic import BaseModel

from lotscope.subdivision.analysis import LimitingFactor


class SubdivisionResult(BaseModel):
    parcel_number: str
    district_code: str | None
    can_subdivide: bool
    max_lots: int | None
    limiting_factor: LimitingFactor | None
    is_conforming: bool | None
    needs_consolidation: bool
    lot_area_sqft: float | None
    lot_width_ft: float | None
    min_lot_area_sqft: float | None
    min_lot_width_ft: float | None
    overlays: list[str]
    reasons: list[str]
    sources: list[dict[str, Any]]
    computed_at: datetime
