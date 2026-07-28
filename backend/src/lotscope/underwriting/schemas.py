from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_ASSUMPTIONS = 60
_FRACTION_SUFFIXES = ("_pct", "_margin", "_rate")


class BuyBox(BaseModel):
    markets: list[str] = Field(default_factory=list, max_length=10)
    property_types: list[str] = Field(default_factory=list, max_length=20)
    min_units: int | None = Field(default=None, ge=0, le=500)
    max_units: int | None = Field(default=None, ge=0, le=500)
    max_acquisition_price: float | None = Field(default=None, ge=0)
    min_margin: float | None = Field(default=None, ge=0, lt=1)
    risk_tolerance: str | None = Field(default=None, max_length=20)
    variance_tolerance: str | None = Field(default=None, max_length=20)
    excluded_conditions: list[str] = Field(default_factory=list, max_length=20)


class ProfileWrite(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    is_default: bool = False
    assumptions: dict[str, float] = Field(default_factory=dict)
    buy_box: BuyBox = Field(default_factory=BuyBox)

    @field_validator("assumptions")
    @classmethod
    def _validate_assumptions(cls, value: dict[str, float]) -> dict[str, float]:
        if len(value) > _MAX_ASSUMPTIONS:
            raise ValueError(f"A profile carries at most {_MAX_ASSUMPTIONS} assumptions.")
        for name, number in value.items():
            if name.endswith(_FRACTION_SUFFIXES) and not 0.0 <= number <= 1.0:
                raise ValueError(f"{name} must be a fraction in [0, 1], got {number!r}.")
            if number < 0:
                raise ValueError(f"{name} cannot be negative.")
        return value

    @field_validator("name")
    @classmethod
    def _trim(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A profile needs a name.")
        return cleaned


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_default: bool
    version: int
    assumptions: dict[str, float]
    buy_box: BuyBox
    created_at: datetime
    updated_at: datetime


class BuyBoxMatch(BaseModel):
    parcel_number: str
    address: str | None = None
    opportunity_score: float | None = None
    max_allowable_offer: float | None = None
    est_margin: float | None = None
    by_right_units: int | None = None
    risk_score: float | None = None


class BuyBoxMatches(BaseModel):
    market: str
    total: int
    matches: list[BuyBoxMatch]
    criteria_applied: list[str]
    has_profile: bool
