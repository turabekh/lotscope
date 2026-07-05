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
    "source_config": {
        "carto_sql_url": "https://phl.carto.com/api/v2/sql",
        "arcgis_hub_url": "https://data-phl.opendata.arcgis.com",
    },
    "coverage_note": None,
    "launch_status": "live",
}

HARRISBURG: dict[str, Any] = {
    "code": "hbg",
    "name": "Harrisburg",
    "state": "PA",
    "url_slug": "harrisburg",
    "local_srid": 2272,
    "map_center": [-76.8844, 40.2732],
    "map_bounds": [[-76.9200, 40.2450], [-76.8500, 40.2950]],
    "default_zoom": 13.5,
    "timezone": "America/New_York",
    "recorder_url_template": (
        "https://www.dauphinpropertyinfo.org/search/CommonSearch.aspx?mode=REALPROP"
    ),
    "deal_assumption_overrides": {"deal_construction_cost_per_sqft": 145.0},
    "source_config": {
        "arcgis_services_url": (
            "https://services2.arcgis.com/EEtiX55QzkHKYQKY/arcgis/rest/services"
        ),
        "municipality_filter": "CITY OF HARRISBURG",
    },
    "coverage_note": (
        "Harrisburg city pilot — county assessment + geometry; no open sale-price comps "
        "and no code-enforcement feed; zoning provisional pending review."
    ),
    "launch_status": "pilot",
}


def market_source_url(source_config: dict[str, Any], key: str, settings: Any) -> str | None:
    value = source_config.get(key)
    if value:
        return str(value)
    return getattr(settings, key, None)

_SEED_MARKETS: tuple[dict[str, Any], ...] = (PHILADELPHIA, HARRISBURG)


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
