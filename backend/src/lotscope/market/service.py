from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.market.schemas import MarketContext

_DAYS_PER_YEAR = 365

_HAS_GEOM_SQL = text(
    "SELECT (geom_local IS NOT NULL) AS has_geometry "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_NEIGHBORHOOD_SQL = text(
    "SELECT n.name FROM parcel p "
    "JOIN neighborhood n ON ST_Contains(n.geom_local, ST_Centroid(p.geom_local)) "
    "WHERE p.parcel_number = :parcel_number LIMIT 1"
)
_CONTEXT_SQL = text(
    "WITH subj AS (SELECT geom_local FROM parcel WHERE parcel_number = :parcel_number), "
    "nearby AS ("
    "  SELECT p.parcel_number, p.is_vacant, p.market_value "
    "  FROM parcel p, subj WHERE ST_DWithin(p.geom_local, subj.geom_local, :radius)"
    ") "
    "SELECT "
    "(SELECT count(*) FROM nearby) AS parcels_nearby, "
    "(SELECT count(*) FROM nearby WHERE is_vacant IS TRUE) AS vacant_nearby, "
    "(SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY market_value) "
    "  FROM nearby WHERE market_value > 0) AS median_assessed, "
    "(SELECT count(*) FROM sale s WHERE s.parcel_number IN (SELECT parcel_number FROM nearby) "
    "  AND s.sale_date >= :since AND s.sale_price > 0) AS recent_sales, "
    "(SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY s.sale_price) FROM sale s "
    "  WHERE s.parcel_number IN (SELECT parcel_number FROM nearby) "
    "  AND s.sale_date >= :since AND s.sale_price > 0) AS median_price, "
    "(SELECT count(*) FROM li_event e WHERE e.parcel_number IN (SELECT parcel_number FROM nearby) "
    "  AND e.event_type = 'permit' AND e.event_date >= :since) AS permits, "
    "(SELECT count(*) FROM li_event e WHERE e.parcel_number IN (SELECT parcel_number FROM nearby) "
    "  AND e.event_type = 'demolition' AND e.event_date >= :since) AS demolitions"
)

_SOURCES: list[dict[str, Any]] = [
    {"source": "rtt_summary"},
    {"source": "li_event"},
    {"source": "opa_properties_public"},
    {"source": "neighborhoods"},
]


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_parcel_market(
    session: AsyncSession,
    parcel_number: str,
    *,
    radius_ft: float = 1500.0,
    years: int = 3,
    since: date | None = None,
) -> MarketContext | None:
    parcel = (await session.execute(_HAS_GEOM_SQL, {"parcel_number": parcel_number})).one_or_none()
    if parcel is None:
        return None
    computed_at = datetime.now(UTC)

    empty = MarketContext(
        parcel_number=parcel_number,
        neighborhood=None,
        radius_ft=radius_ft,
        years=years,
        parcels_nearby=0,
        vacant_nearby=0,
        vacancy_rate=None,
        median_assessed_value=None,
        recent_sales=0,
        sales_per_year=None,
        median_sale_price=None,
        permits=0,
        demolitions=0,
        sources=_SOURCES,
        computed_at=computed_at,
    )
    if not parcel.has_geometry:
        return empty

    cutoff = (
        since if since is not None else computed_at.date() - timedelta(days=years * _DAYS_PER_YEAR)
    )
    params = {"parcel_number": parcel_number, "radius": radius_ft, "since": cutoff}
    row = (await session.execute(_CONTEXT_SQL, params)).one()
    neighborhood = await session.scalar(_NEIGHBORHOOD_SQL, {"parcel_number": parcel_number})

    parcels_nearby = int(row.parcels_nearby or 0)
    recent_sales = int(row.recent_sales or 0)
    return MarketContext(
        parcel_number=parcel_number,
        neighborhood=neighborhood,
        radius_ft=radius_ft,
        years=years,
        parcels_nearby=parcels_nearby,
        vacant_nearby=int(row.vacant_nearby or 0),
        vacancy_rate=(
            round(int(row.vacant_nearby or 0) / parcels_nearby, 4) if parcels_nearby else None
        ),
        median_assessed_value=_as_float(row.median_assessed),
        recent_sales=recent_sales,
        sales_per_year=round(recent_sales / years, 1) if years else None,
        median_sale_price=_as_float(row.median_price),
        permits=int(row.permits or 0),
        demolitions=int(row.demolitions or 0),
        sources=_SOURCES,
        computed_at=computed_at,
    )
