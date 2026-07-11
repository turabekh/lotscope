from datetime import date, datetime

from pydantic import BaseModel


class BuyerStats(BaseModel):
    buyer_key: str
    display_name: str
    purchases_window: int
    lot_purchases_window: int
    last_purchase_at: date | None
    median_price: float | None
    total_consideration: float | None
    mailing_address: str | None


class NearbyBuyer(BuyerStats):
    distance_ft: float


class BuyersNearby(BaseModel):
    market_code: str
    available: bool
    note: str | None = None
    radius_ft: float
    computed_at: datetime | None = None
    buyers: list[NearbyBuyer]


class BuyerRoster(BaseModel):
    market_code: str
    available: bool
    note: str | None = None
    total: int
    returned: int
    buyers: list[BuyerStats]


class BuyerPurchase(BaseModel):
    parcel_number: str
    address: str | None
    sale_date: date | None
    sale_price: float | None
    is_vacant: bool | None


class BuyerProfileDetail(BuyerStats):
    market_code: str
    computed_at: datetime | None
    purchases: list[BuyerPurchase]
