from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class UserCreate(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    role: str
    tier: str
    is_active: bool
    subscription_status: str | None
    digest_frequency: str
    created_at: datetime


class DigestPreference(BaseModel):
    frequency: Literal["off", "weekly", "daily"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UsageMetric(BaseModel):
    limit: int | None
    used: int
    remaining: int | None


class UsageResponse(BaseModel):
    tier: str
    ask: UsageMetric
    parcel_views: UsageMetric


class CheckoutRequest(BaseModel):
    tier: Literal["pro", "investor"] = "pro"
    cadence: Literal["monthly", "annual"] = "monthly"


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


class PlanInfo(BaseModel):
    tier: str
    name: str
    tagline: str
    price_monthly_cents: int | None
    price_annual_cents: int | None
    action: Literal["current", "checkout", "contact"]
    highlights: list[str]
    is_current: bool


class PlansResponse(BaseModel):
    plans: list[PlanInfo]
    contact_url: str
