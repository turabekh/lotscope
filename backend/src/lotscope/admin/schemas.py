from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from lotscope.accounts.schemas import UserRead


class DatasetStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_code: str
    dataset: str
    status: str
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    row_count: int | None
    detail: str | None


class AdminOverview(BaseModel):
    users_total: int
    users_by_tier: dict[str, int]
    parcels_total: int
    parcels_vacant: int
    verdicts_total: int
    deeds_total: int
    saved_searches_total: int
    neighborhoods_total: int


class AdminUsersResponse(BaseModel):
    total: int
    users: list[UserRead]


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    tier: Literal["free", "pro", "investor", "enterprise"] | None = None
    is_active: bool | None = None


class JobRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    label: str
    kind: str
    market_code: str | None
    params: dict[str, str] | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    result_count: int | None
    error: str | None
    triggered_by: int
    created_at: datetime


class JobParamSpec(BaseModel):
    name: str
    label: str
    type: str
    required: bool


class JobCatalogEntry(BaseModel):
    id: str
    label: str
    kind: str
    description: str
    market: str | None
    dataset: str | None
    params: list[JobParamSpec]
    latest_run: JobRunSummary | None


class JobRunRequest(BaseModel):
    job_id: str
    params: dict[str, str] = {}
