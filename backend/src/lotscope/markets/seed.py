from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.markets.models import Market

PHILADELPHIA: dict[str, Any] = {
    "code": "phl",
    "name": "Philadelphia",
    "state": "PA",
    "url_slug": "philadelphia",
    "local_srid": 2272,
    "map_center": [-75.1652, 39.9526],
    "map_bounds": None,
    "default_zoom": 13.0,
    "timezone": "America/New_York",
    "recorder_url_template": (
        "https://epay.phila-records.com/phillyepay/web/integration/document/"
        "InstrumentID={document_id}&Guest=true"
    ),
    "deal_assumption_overrides": {},
    "coverage_note": None,
    "launch_status": "live",
}

_SEED_MARKETS: tuple[dict[str, Any], ...] = (PHILADELPHIA,)


async def seed_markets(session: AsyncSession) -> int:
    count = 0
    for row in _SEED_MARKETS:
        existing = await session.get(Market, row["code"])
        if existing is None:
            session.add(Market(**row))
            count += 1
        else:
            for key, value in row.items():
                setattr(existing, key, value)
    await session.flush()
    return count


async def market_exists(session: AsyncSession, code: str) -> bool:
    result = await session.execute(select(Market.code).where(Market.code == code))
    return result.scalar_one_or_none() is not None
