from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParcelDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parcel_number: str
    market_code: str
    local_key: str
    address: str | None
    zip_code: str | None
    owner: str | None
    mailing_address: str | None
    land_use: str | None
    category: str | None
    base_zoning_code: str | None
    resolved_zoning_code: str | None = None
    zoning_resolution: str | None = None
    market_value: float | None
    land_value: float | None
    improvement_value: float | None
    exempt_land: float | None
    exempt_building: float | None
    assessment_year: int | None
    assessment_ratio: float | None = None
    lot_area_sqft: float | None
    lot_area_source: str | None = None
    frontage_ft: float | None
    depth_ft: float | None
    is_vacant: bool | None
    vacancy_confidence: float | None
    is_city_owned: bool | None
    source: str | None
    last_synced_at: datetime | None
    longitude: float | None = None
    latitude: float | None = None
