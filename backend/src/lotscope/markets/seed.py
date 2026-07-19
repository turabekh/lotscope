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
    "assessment_ratio": 1.0,
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
    "assessment_ratio": 0.4042,
}


PITTSBURGH: dict[str, Any] = {
    "code": "pgh",
    "name": "Pittsburgh",
    "state": "PA",
    "url_slug": "pittsburgh",
    "local_srid": 2272,
    "map_center": [-79.9959, 40.4406],
    "map_bounds": [[-80.0954, 40.3610], [-79.8656, 40.5012]],
    "default_zoom": 12.5,
    "timezone": "America/New_York",
    "recorder_url_template": (
        "https://gis.alleghenycounty.us/RealEstate/SearchResults.aspx?ParcelID={local_key}"
    ),
    "deal_assumption_overrides": {},
    "source_config": {
        "ckan_base_url": "https://data.wprdc.org",
        "municipality_filter": "PITTSBURGH",
        "assessment_resource_id": "65855e14-549e-4992-b5be-d629afc676fa",
        "boundaries_resource_id": "3f50d47a-ab54-4da2-9f03-8519006e9fc9",
        "sales_resource_id": "5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1",
        "liens_resource_id": "d1e80180-5b2e-4dab-8ec3-be621628649e",
        "violations_resource_id": "70c06278-92c5-4040-ab28-17671866f81c",
        "condemned_resource_id": "0a963f26-eb4b-4325-bbbc-3ddf6a871410",
        "city_owned_resource_id": "e1dcee82-9179-4306-8167-5891915b62a7",
        "foreclosures_resource_id": "859bccfd-0e12-4161-a348-313d734f25fd",
        "zoning_resource_id": "6127f35e-f36b-4a53-80b3-f4409609e9df",
        "neighborhoods_resource_id": "4af8e160-57e9-4ebf-a501-76ca1b42fc99",
    },
    "coverage_note": (
        "Pittsburgh city pilot — Allegheny County assessment + geometry via WPRDC; "
        "validation-filtered sale comps; PLI violations live; owner surfaces disabled "
        "(Ordinance 3478-07); zoning provisional pending review."
    ),
    "launch_status": "pilot",
    "assessment_ratio": 0.5014,
}


WILMINGTON: dict[str, Any] = {
    "code": "wlm",
    "name": "Wilmington",
    "state": "DE",
    "url_slug": "wilmington",
    "local_srid": 2235,
    "map_center": [-75.5466, 39.7459],
    "map_bounds": [[-75.5900, 39.7100], [-75.4950, 39.7850]],
    "default_zoom": 13.0,
    "timezone": "America/New_York",
    "recorder_url_template": "https://www3.newcastlede.gov/parcel/search/",
    "deal_assumption_overrides": {},
    "source_config": {
        "firstmap_parcels_url": (
            "https://enterprise.firstmap.delaware.gov/arcgis/rest/services/"
            "PlanningCadastre/DE_StateParcels/FeatureServer/0"
        ),
        "wilmington_arcgis_url": (
            "https://services.arcgis.com/hQ3wdpbjO3fPf612/arcgis/rest/services"
        ),
        "sheriff_civilview_county_id": "24",
        "hundred_filter": "26",
    },
    "coverage_note": (
        "Wilmington city pilot — New Castle County (DE) assessment + FirstMap geometry; "
        "FMV-2024 reassessment (ratio ~1.0); reduced distress stack (sheriff, tax, flood, "
        "land bank; no open code-violation or vacancy feed); comps sourcing provisional; "
        "zoning from City GIS."
    ),
    "launch_status": "pilot",
    "assessment_ratio": 1.0,
}


def market_source_url(source_config: dict[str, Any], key: str, settings: Any) -> str | None:
    value = source_config.get(key)
    if value:
        return str(value)
    return getattr(settings, key, None)


_SEED_MARKETS: tuple[dict[str, Any], ...] = (PHILADELPHIA, HARRISBURG, PITTSBURGH, WILMINGTON)


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
