from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SearchCriteria(BaseModel):
    vacant_only: bool = False
    exclude_city_owned: bool = True
    zoning_codes: list[str] = Field(default_factory=list, max_length=40)
    zip_code: str | None = Field(default=None, max_length=10)
    min_market_value: float | None = Field(default=None, ge=0)
    max_market_value: float | None = Field(default=None, ge=0)
    min_lot_area_sqft: float | None = Field(default=None, ge=0)
    max_lot_area_sqft: float | None = Field(default=None, ge=0)
    min_opportunity_score: int | None = Field(default=None, ge=0, le=100)
    min_distress_score: int | None = Field(default=None, ge=0, le=100)
    is_delinquent: bool | None = None
    in_sheriff_sale: bool | None = None

    @field_validator("zoning_codes")
    @classmethod
    def _normalize_codes(cls, codes: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for code in codes:
            cleaned = code.strip().upper()
            if cleaned:
                seen.setdefault(cleaned, None)
        return list(seen)

    @field_validator("zip_code")
    @classmethod
    def _normalize_zip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    criteria: SearchCriteria = Field(default_factory=SearchCriteria)
    alerts_enabled: bool = True


class SavedSearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    criteria: SearchCriteria | None = None
    alerts_enabled: bool | None = None


class SavedSearchMatchItem(BaseModel):
    parcel_number: str
    address: str | None
    owner: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None
    first_seen_at: datetime
    is_new: bool


class SavedSearchItem(BaseModel):
    id: int
    name: str
    criteria: SearchCriteria
    alerts_enabled: bool
    created_at: datetime
    last_run_at: datetime | None
    match_count: int
    new_count: int


class SavedSearchDetail(SavedSearchItem):
    matches: list[SavedSearchMatchItem] = Field(default_factory=list)


class SavedSearchListResponse(BaseModel):
    limit: int | None
    used: int
    searches: list[SavedSearchItem]


class SavedSearchAlert(BaseModel):
    search_id: int
    name: str
    new_matches: list[SavedSearchMatchItem]
