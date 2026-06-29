from pydantic import BaseModel


class OwnerParcel(BaseModel):
    parcel_number: str
    address: str | None
    base_zoning_code: str | None
    is_vacant: bool | None
    market_value: float | None
    opportunity_score: int | None


class OwnerPortfolio(BaseModel):
    owner: str | None
    mailing_address: str | None
    total_count: int
    vacant_count: int
    total_market_value: float | None
    shown: int
    parcels: list[OwnerParcel]
