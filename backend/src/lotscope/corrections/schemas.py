from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CorrectionStatus = Literal["open", "triaged", "resolved", "rejected"]
CorrectionSection = Literal[
    "verdict", "buildability", "valuation", "deal", "risk", "ownership", "other"
]

_OPEN_STATES: frozenset[str] = frozenset({"open", "triaged"})
_TERMINAL_STATES: frozenset[str] = frozenset({"resolved", "rejected"})
_MAX_DESCRIPTION = 4000


class CorrectionCreate(BaseModel):
    section: CorrectionSection
    field_name: str | None = Field(default=None, max_length=60)
    description: str = Field(min_length=10, max_length=_MAX_DESCRIPTION)
    attachment_ref: str | None = Field(default=None, max_length=500)

    @field_validator("description")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("Describe what is wrong in at least 10 characters.")
        return cleaned


class CorrectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parcel_number: str
    market_code: str
    reported_by: int
    section: str
    field_name: str | None
    verdict_computed_at: datetime | None
    field_status: str | None
    source_label: str | None
    source_as_of: datetime | None
    description: str
    attachment_ref: str | None
    status: str
    resolution: str | None
    resolved_at: datetime | None
    created_at: datetime


class CorrectionResolve(BaseModel):
    status: CorrectionStatus
    resolution: str | None = Field(default=None, max_length=_MAX_DESCRIPTION)
