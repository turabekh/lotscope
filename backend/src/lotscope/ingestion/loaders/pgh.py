from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.ckan import CkanDatastoreClient
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

PGH_PARCELS_DATASET = "pgh_assessment"
PGH_GEOMETRY_DATASET = "pgh_boundaries"
_MARKET = "pgh"
_LOCAL_SRID = 2272
_CITY_WHERE = "\"MUNIDESC\" ILIKE '%PITTSBURGH%'"

_ASSESSMENT_COLUMNS = (
    '"PARID"',
    '"PROPERTYADDRESS"',
    '"PROPERTYZIP"',
    '"USEDESC"',
    '"COUNTYTOTAL"',
    '"COUNTYLAND"',
    '"COUNTYBUILDING"',
    '"LOTAREA"',
    '"MUNIDESC"',
)

_UPDATE_COLUMNS = [
    "market_code",
    "coverage",
    "address",
    "zip_code",
    "land_use",
    "market_value",
    "land_value",
    "improvement_value",
    "lot_area_sqft",
    "lot_area_source",
]


def _txt(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def _num(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _parcel_row(record: dict[str, Any]) -> dict[str, Any] | None:
    local = get_normalizer(_MARKET).normalize_local_key(record.get("PARID"))
    if local is None:
        return None
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "market_code": _MARKET,
        "coverage": "full",
        "address": _txt(record.get("PROPERTYADDRESS")),
        "zip_code": _txt(record.get("PROPERTYZIP")),
        "land_use": _txt(record.get("USEDESC")),
        "market_value": _num(record.get("COUNTYTOTAL")),
        "land_value": _num(record.get("COUNTYLAND")),
        "improvement_value": _num(record.get("COUNTYBUILDING")),
        "lot_area_sqft": _num(record.get("LOTAREA")),
        "lot_area_source": "extract",
    }


async def load_pgh_parcels(
    session: AsyncSession,
    ckan: CkanDatastoreClient,
    *,
    resource_id: str,
    page_size: int = 5000,
) -> int:
    total = 0
    async for records in ckan.paginate_by_key(
        resource_id=resource_id,
        columns=_ASSESSMENT_COLUMNS,
        key_column='"PARID"',
        page_size=page_size,
        where=_CITY_WHERE,
    ):
        rows = [row for row in (_parcel_row(r) for r in records) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=_UPDATE_COLUMNS,
            )
            total += len(rows)
    await record_freshness(
        session, PGH_PARCELS_DATASET, status="success", success=True,
        market_code=_MARKET, row_count=total,
    )
    return total


async def _pittsburgh_municodes(ckan: CkanDatastoreClient, resource_id: str) -> list[str]:
    rows = await ckan.query(
        f'SELECT DISTINCT "MUNICODE" FROM "{resource_id}" WHERE {_CITY_WHERE}'
    )
    return sorted({str(r["MUNICODE"]) for r in rows if r.get("MUNICODE") is not None})


def _geometry_row(record: dict[str, Any]) -> dict[str, Any] | None:
    local = get_normalizer(_MARKET).normalize_local_key(record.get("PIN"))
    wkb_hex = _txt(record.get("wkb_hex"))
    if local is None or wkb_hex is None:
        return None
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromWKB(func.decode(wkb_hex, "hex")), 4326)
    return {
        "parcel_number": f"{_MARKET}:{local}",
        "market_code": _MARKET,
        "geom_4326": geom_4326,
        "geom_local": func.ST_Transform(geom_4326, _LOCAL_SRID),
    }


async def load_pgh_geometry(
    session: AsyncSession,
    ckan: CkanDatastoreClient,
    *,
    boundaries_resource_id: str,
    assessment_resource_id: str,
    page_size: int = 4000,
) -> int:
    municodes = await _pittsburgh_municodes(ckan, assessment_resource_id)
    muni_list = ", ".join(f"'{m}'" for m in municodes) or "''"
    columns = ('"PIN"', 'encode("dataspatial_wkb", \'hex\') AS wkb_hex')
    total = 0
    async for records in ckan.paginate_by_key(
        resource_id=boundaries_resource_id,
        columns=columns,
        key_column='"PIN"',
        page_size=page_size,
        where=f'"MUNICODE" IN ({muni_list})',
    ):
        rows = [row for row in (_geometry_row(r) for r in records) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=["geom_4326", "geom_local"],
            )
            total += len(rows)
    await record_freshness(
        session, PGH_GEOMETRY_DATASET, status="success", success=True,
        market_code=_MARKET, row_count=total,
    )
    return total
