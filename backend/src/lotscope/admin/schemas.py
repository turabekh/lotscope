from datetime import date, datetime
from decimal import Decimal
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
    screened_total: int
    deeds_total: int
    neighborhoods_total: int


class AdminUsersResponse(BaseModel):
    total: int
    users: list[UserRead]


class AdminUserUpdate(BaseModel):
    role: Literal["user", "admin"] | None = None
    tier: Literal["free", "pro", "investor", "enterprise"] | None = None
    is_active: bool | None = None
    # Sent explicitly as null to hand the account back to the platform default, which is
    # why these are read through model_fields_set rather than "is not None".
    analyst_daily_usd: Decimal | None = None
    analyst_daily_runs: int | None = None


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
    duration_ms: int | None = None
    error: str | None
    triggered_by: int
    created_at: datetime


class AnalystSpendRow(BaseModel):
    user_id: int
    email: str
    chat_usd: Decimal
    job_usd: Decimal
    total_usd: Decimal
    runs: int
    input_tokens: int
    output_tokens: int
    ceiling_usd: Decimal
    run_ceiling: int
    over_ceiling: bool


class AnalystSpendToday(BaseModel):
    """What the Analyst has cost today, per buyer and in total.

    `usd_estimate` throughout: token counts are exact, list prices are what we assume.
    """

    day: date
    spend_usd: Decimal
    global_ceiling_usd: Decimal
    fraction: float
    default_ceiling_usd: Decimal
    default_run_ceiling: int
    users: list[AnalystSpendRow]


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
