from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.logging import get_logger

logger = get_logger(__name__)

_REFRESH_SQL = text(
    "INSERT INTO parcel_overlay "
    "(market_code, parcel_number, overlay_id, overlay_code, overlay_name, code_section) "
    "SELECT p.market_code, p.parcel_number, zo.id, zo.code, zo.name, zo.code_section "
    "FROM parcel p "
    "JOIN zoning_overlay zo ON zo.market_code = p.market_code "
    "AND ST_Intersects(zo.geom_local, p.geom_local) "
    "WHERE p.market_code = :market_code AND p.geom_local IS NOT NULL"
)

_CLEAR_SQL = text("DELETE FROM parcel_overlay WHERE market_code = :market_code")

_COUNT_SQL = text("SELECT count(*) FROM parcel_overlay WHERE market_code = :market_code")

_DIVERGENCE_SQL = text(
    "SELECT count(*) AS divergent FROM ( "
    "  SELECT p.parcel_number, zo.id FROM parcel p "
    "  JOIN zoning_overlay zo ON zo.market_code = p.market_code "
    "  AND ST_Intersects(zo.geom_local, p.geom_local) "
    "  WHERE p.market_code = :market_code AND p.geom_local IS NOT NULL "
    "  AND p.parcel_number = ANY(:parcel_numbers) "
    "  EXCEPT "
    "  SELECT po.parcel_number, po.overlay_id FROM parcel_overlay po "
    "  WHERE po.market_code = :market_code AND po.parcel_number = ANY(:parcel_numbers) "
    ") AS missing"
)


async def refresh_parcel_overlays(session: AsyncSession, market_code: str) -> int:
    await session.execute(_CLEAR_SQL, {"market_code": market_code})
    await session.execute(_REFRESH_SQL, {"market_code": market_code})
    total = await session.scalar(_COUNT_SQL, {"market_code": market_code}) or 0
    logger.info("refreshed_parcel_overlays", market=market_code, rows=total)
    return int(total)


async def parcel_overlay_divergence(
    session: AsyncSession, market_code: str, parcel_numbers: list[str]
) -> int:
    if not parcel_numbers:
        return 0
    divergent = await session.scalar(
        _DIVERGENCE_SQL, {"market_code": market_code, "parcel_numbers": parcel_numbers}
    )
    return int(divergent or 0)
