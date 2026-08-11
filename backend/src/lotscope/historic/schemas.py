from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class HistoricResult(BaseModel):
    parcel_number: str
    evaluated: bool
    in_historic_district: bool
    district_name: str | None
    designated_date: date | None
    note: str | None
    sources: list[dict[str, Any]]
    computed_at: datetime
