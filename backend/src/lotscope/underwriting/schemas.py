from pydantic import BaseModel


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
