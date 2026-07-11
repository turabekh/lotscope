from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.markets.models import Market
from lotscope.ops.models import MarketStats
from lotscope.verdict.composition import VERDICT_VERSION

_STATS_SQL = text(
    "SELECT "
    "count(*) AS parcel_count, "
    "100.0 * count(*) FILTER (WHERE p.geom_local IS NOT NULL) "
    "  / nullif(count(*), 0) AS geometry_pct, "
    "100.0 * count(*) FILTER (WHERE v.verdict_version = :vv) "
    "  / nullif(count(*), 0) AS verdict_pct, "
    "count(*) FILTER (WHERE coalesce(p.is_vacant, false)) AS vacant_count, "
    "100.0 * count(*) FILTER (WHERE coalesce(p.is_vacant, false) "
    "  AND v.value_estimate_low IS NOT NULL) "
    "  / nullif(count(*) FILTER (WHERE coalesce(p.is_vacant, false)), 0) AS vacant_with_comp_pct "
    "FROM parcel p LEFT JOIN parcel_verdict v ON v.parcel_number = p.parcel_number "
    "WHERE p.market_code = :market"
)


def _round(value: Any) -> float | None:
    return round(float(value), 2) if value is not None else None


async def snapshot_market_stats(session_factory: async_sessionmaker[AsyncSession]) -> int:
    computed_at = datetime.now(UTC)
    async with session_factory() as session:
        markets = list((await session.execute(select(Market.code))).scalars())
        for market in markets:
            params = {"market": market, "vv": VERDICT_VERSION}
            row = (await session.execute(_STATS_SQL, params)).one()
            values = {
                "market_code": market,
                "parcel_count": int(row.parcel_count or 0),
                "geometry_pct": _round(row.geometry_pct),
                "verdict_pct": _round(row.verdict_pct),
                "vacant_count": int(row.vacant_count or 0),
                "vacant_with_comp_pct": _round(row.vacant_with_comp_pct),
                "computed_at": computed_at,
            }
            statement = insert(MarketStats).values(**values)
            update_cols: dict[str, Any] = {
                key: statement.excluded[key] for key in values if key != "market_code"
            }
            update_cols["updated_at"] = func.now()
            statement = statement.on_conflict_do_update(
                index_elements=["market_code"], set_=update_cols
            )
            await session.execute(statement)
        await session.commit()
    return len(markets)
