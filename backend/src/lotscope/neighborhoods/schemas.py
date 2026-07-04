from datetime import datetime

from pydantic import BaseModel


class NeighborhoodSummary(BaseModel):
    name: str


class NeighborhoodListResponse(BaseModel):
    neighborhoods: list[NeighborhoodSummary]


class NeighborhoodMarketStats(BaseModel):
    name: str
    vacant_lots: int
    avg_distress: float | None
    avg_opportunity: float | None
    median_market_value: float | None
    tax_delinquent: int
    sheriff_sale: int


class MarketTotals(BaseModel):
    neighborhoods: int
    vacant_lots: int
    tax_delinquent: int
    sheriff_sale: int


class NeighborhoodMarketResponse(BaseModel):
    totals: MarketTotals
    neighborhoods: list[NeighborhoodMarketStats]
    computed_at: datetime
