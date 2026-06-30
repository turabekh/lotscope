from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MarketContext(BaseModel):
    parcel_number: str
    neighborhood: str | None
    radius_ft: float
    years: int
    parcels_nearby: int
    vacant_nearby: int
    vacancy_rate: float | None
    median_assessed_value: float | None
    recent_sales: int
    sales_per_year: float | None
    median_sale_price: float | None
    permits: int
    demolitions: int
    sources: list[dict[str, Any]]
    computed_at: datetime
