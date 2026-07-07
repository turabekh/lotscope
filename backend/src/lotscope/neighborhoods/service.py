from datetime import UTC, datetime
from typing import Any

from sqlalchemy import distinct, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.neighborhoods.models import Neighborhood
from lotscope.neighborhoods.schemas import (
    MarketTotals,
    NeighborhoodMarketResponse,
    NeighborhoodMarketStats,
    NeighborhoodSummary,
)

_MARKET_STATS_SQL = text(
    "SELECT n.name, "
    "count(*) AS vacant_lots, "
    "avg(pd.score) AS avg_distress, "
    "avg(pv.opportunity_score) AS avg_opportunity, "
    "percentile_cont(0.5) WITHIN GROUP (ORDER BY p.market_value) AS median_market_value, "
    "count(*) FILTER (WHERE ts.is_delinquent) AS tax_delinquent, "
    "count(*) FILTER (WHERE ts.in_sheriff_sale) AS sheriff_sale "
    "FROM neighborhood n "
    "JOIN parcel p ON p.is_vacant AND p.geom_local IS NOT NULL "
    "  AND p.market_code = n.market_code "
    "  AND ST_Contains(n.geom_local, ST_Centroid(p.geom_local)) "
    "LEFT JOIN parcel_distress pd ON pd.parcel_number = p.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "WHERE n.market_code = :market "
    "GROUP BY n.name "
    "ORDER BY vacant_lots DESC, n.name"
)


async def list_neighborhoods(session: AsyncSession, market_code: str) -> list[NeighborhoodSummary]:
    rows = (
        await session.execute(
            select(distinct(Neighborhood.name))
            .where(Neighborhood.name.isnot(None), Neighborhood.market_code == market_code)
            .order_by(Neighborhood.name)
        )
    ).all()
    return [NeighborhoodSummary(name=row[0]) for row in rows]


def _round(value: Any, digits: int = 1) -> float | None:
    return round(float(value), digits) if value is not None else None


async def neighborhood_market_stats(
    session: AsyncSession, market_code: str
) -> NeighborhoodMarketResponse:
    rows = (await session.execute(_MARKET_STATS_SQL, {"market": market_code})).all()
    neighborhoods = [
        NeighborhoodMarketStats(
            name=row.name,
            vacant_lots=int(row.vacant_lots),
            avg_distress=_round(row.avg_distress),
            avg_opportunity=_round(row.avg_opportunity),
            median_market_value=_round(row.median_market_value, 0),
            tax_delinquent=int(row.tax_delinquent),
            sheriff_sale=int(row.sheriff_sale),
        )
        for row in rows
    ]
    totals = MarketTotals(
        neighborhoods=len(neighborhoods),
        vacant_lots=sum(item.vacant_lots for item in neighborhoods),
        tax_delinquent=sum(item.tax_delinquent for item in neighborhoods),
        sheriff_sale=sum(item.sheriff_sale for item in neighborhoods),
    )
    return NeighborhoodMarketResponse(
        totals=totals, neighborhoods=neighborhoods, computed_at=datetime.now(UTC)
    )
