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
