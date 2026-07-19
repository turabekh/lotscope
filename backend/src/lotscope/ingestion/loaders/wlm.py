import json
import re
from datetime import date
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel
from lotscope.valuation.models import Sale

WLM_PARCELS_DATASET = "firstmap_parcels"
WLM_ASSESSMENT_DATASET = "wilmington_assessment"
WLM_ZONING_DATASET = "wilmington_zoning"
WLM_COMPS_DATASET = "wilmington_comps"
_MARKET = "wlm"
_LOCAL_SRID = 2235

_WILMINGTON_PARCELS_LAYER = "LUP_Map_w_RISE_STAR_Bldg_Code_Enf_and_DDD_WFL1/FeatureServer/0"
_ASSESSMENT_FIELDS = "PRCLID,OWNER,OWNRADD1,OWNRADD2,ASMTLAND,ASMTSTRT,PROP_CLASS"
_ZONING_FIELDS = "PRCLID,ZONECODE"
_COMPS_FIELDS = "PRCLID,SALEPRC,SALEYR,SALEMON"

_LAST_SALE_DOCUMENT_ID = "wlm_assessment_last_sale"
_LAST_SALE_DOCUMENT_TYPE = "assessment_last_sale"
_SALE_YEAR_PIVOT = 40


def _wlm_sale_date(raw_year: Any, raw_month: Any) -> date | None:
    try:
        year = int(raw_year)
    except (TypeError, ValueError):
        return None
    if year < 1 or year > 99:
        return None
    full_year = 2000 + year if year <= _SALE_YEAR_PIVOT else 1900 + year
    try:
        month = int(raw_month)
    except (TypeError, ValueError):
        month = 0
    return date(full_year, month if 1 <= month <= 12 else 1, 1)


_HUNDRED_PREFIX = "26"
_ZONE_RE = re.compile(r"^([RCMW])(\d+)([A-Z0-9]*)$")


def normalize_wilmington_zone(raw: str | None) -> str | None:
    if raw is None:
        return None
    cleaned = "".join(str(raw).split()).upper()
    if cleaned.startswith(_HUNDRED_PREFIX):
        cleaned = cleaned[len(_HUNDRED_PREFIX) :]
    cleaned = cleaned.replace("-", "")
    if not cleaned:
        return None
    if cleaned == "O":
        return "O"
    match = _ZONE_RE.match(cleaned)
    if match is None:
        return None
    zone_class, number, suffix = match.groups()
    return f"{zone_class}-{number}{suffix}"


_PARCEL_UPDATE_COLUMNS = [
    "coverage",
    "lot_area_sqft",
    "lot_area_source",
    "geom_local",
    "geom_4326",
]
_ASSESSMENT_UPDATE_COLUMNS = [
    "owner",
    "mailing_address",
    "category",
    "land_value",
    "improvement_value",
    "market_value",
]
_ZONING_UPDATE_COLUMNS = ["base_zoning_code"]


def _txt(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _num(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _mailing(props: dict[str, Any]) -> str | None:
    return _txt(" ".join(str(props.get(field) or "") for field in ("OWNRADD1", "OWNRADD2")))


def wilmington_parcels_layer_url(arcgis_base_url: str) -> str:
    return f"{arcgis_base_url.rstrip('/')}/{_WILMINGTON_PARCELS_LAYER}"


def to_wlm_parcel_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    key = get_normalizer(_MARKET).to_canonical(feature.properties.get("PIN"))
    if key is None or feature.geometry is None:
        return None
    geom_local = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), _LOCAL_SRID)
    return {
        "parcel_number": key,
        "market_code": _MARKET,
        "coverage": "full",
        "lot_area_sqft": func.ST_Area(geom_local),
        "lot_area_source": "geometry",
        "geom_local": geom_local,
        "geom_4326": func.ST_Transform(geom_local, 4326),
    }


async def load_wlm_parcels(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    parcels_url: str,
    hundred: str,
    page_size: int = 2000,
) -> int:
    if not hundred.isdigit():
        raise IngestionError(f"Wilmington hundred filter must be numeric, got {hundred!r}.")
    layer = f"{parcels_url}/query"
    where = f"PIN LIKE '{hundred}%'"
    total = 0
    async for features in arcgis.paginate(
        layer, where=where, out_fields="PIN", out_sr=_LOCAL_SRID, page_size=page_size
    ):
        rows = [row for row in (to_wlm_parcel_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=_PARCEL_UPDATE_COLUMNS,
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_PARCELS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def to_wlm_assessment_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    key = get_normalizer(_MARKET).to_canonical(props.get("PRCLID"))
    if key is None:
        return None
    land = _num(props.get("ASMTLAND"))
    improvement = _num(props.get("ASMTSTRT"))
    market = (land or 0.0) + (improvement or 0.0) if (land or improvement) else None
    return {
        "parcel_number": key,
        "market_code": _MARKET,
        "owner": _txt(props.get("OWNER")),
        "mailing_address": _mailing(props),
        "category": _txt(props.get("PROP_CLASS")),
        "land_value": land,
        "improvement_value": improvement,
        "market_value": market,
    }


async def load_wlm_assessment(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    parcels_layer_url: str,
    page_size: int = 2000,
) -> int:
    layer = f"{parcels_layer_url}/query"
    total = 0
    async for features in arcgis.paginate(
        layer, out_fields=_ASSESSMENT_FIELDS, return_geometry=False, page_size=page_size
    ):
        rows = [row for row in (to_wlm_assessment_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=_ASSESSMENT_UPDATE_COLUMNS,
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_ASSESSMENT_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def to_wlm_zoning_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    key = get_normalizer(_MARKET).to_canonical(feature.properties.get("PRCLID"))
    if key is None:
        return None
    return {
        "parcel_number": key,
        "market_code": _MARKET,
        "base_zoning_code": normalize_wilmington_zone(feature.properties.get("ZONECODE")),
    }


async def load_wlm_zoning(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    parcels_layer_url: str,
    page_size: int = 2000,
) -> int:
    layer = f"{parcels_layer_url}/query"
    total = 0
    async for features in arcgis.paginate(
        layer, out_fields=_ZONING_FIELDS, return_geometry=False, page_size=page_size
    ):
        rows = [row for row in (to_wlm_zoning_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=_ZONING_UPDATE_COLUMNS,
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_ZONING_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


def to_wlm_sale_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    key = get_normalizer(_MARKET).to_canonical(props.get("PRCLID"))
    if key is None:
        return None
    price = _num(props.get("SALEPRC"))
    sale_date = _wlm_sale_date(props.get("SALEYR"), props.get("SALEMON"))
    if price is None or sale_date is None:
        return None
    return {
        "parcel_number": key,
        "document_id": _LAST_SALE_DOCUMENT_ID,
        "document_type": _LAST_SALE_DOCUMENT_TYPE,
        "sale_date": sale_date,
        "sale_price": price,
        "grantor": None,
        "grantee": None,
    }


async def _wlm_parcel_numbers(session: AsyncSession) -> set[str]:
    result = await session.execute(
        select(Parcel.parcel_number).where(Parcel.market_code == _MARKET)
    )
    return {row[0] for row in result}


async def load_wlm_comps(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    parcels_layer_url: str,
    page_size: int = 2000,
) -> int:
    known = await _wlm_parcel_numbers(session)
    layer = f"{parcels_layer_url}/query"
    total = 0
    async for features in arcgis.paginate(
        layer, out_fields=_COMPS_FIELDS, return_geometry=False, page_size=page_size
    ):
        rows = [
            row
            for row in (to_wlm_sale_row(f) for f in features)
            if row is not None and row["parcel_number"] in known
        ]
        if rows:
            await upsert(
                session,
                Sale,
                rows,
                index_elements=["parcel_number", "document_id"],
                update_columns=["document_type", "sale_date", "sale_price"],
            )
            total += len(rows)
    await record_freshness(
        session,
        WLM_COMPS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=total,
    )
    return total


WLM_DIMENSIONS_DATASET = "wilmington_dimensions"

_LOT_WIDTH_UPDATE = text(
    "UPDATE parcel p SET frontage_ft = sub.width, updated_at = now() "
    "FROM ("
    "  SELECT parcel_number, LEAST("
    "    ST_Distance(ST_PointN(ring, 1), ST_PointN(ring, 2)),"
    "    ST_Distance(ST_PointN(ring, 2), ST_PointN(ring, 3))"
    "  ) AS width"
    "  FROM ("
    "    SELECT parcel_number, ST_ExteriorRing(ST_OrientedEnvelope(geom_local)) AS ring"
    "    FROM parcel"
    "    WHERE market_code = :market AND geom_local IS NOT NULL AND frontage_ft IS NULL"
    "  ) envelope"
    ") sub "
    "WHERE p.parcel_number = sub.parcel_number AND sub.width > 0"
)


async def derive_wlm_lot_width(session: AsyncSession) -> int:
    executed = await session.execute(_LOT_WIDTH_UPDATE, {"market": _MARKET})
    count = cast("CursorResult[Any]", executed).rowcount or 0
    await record_freshness(
        session,
        WLM_DIMENSIONS_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=count,
    )
    return count


WLM_VACANCY_DATASET = "wilmington_vacancy"
_VACANCY_IMPROVEMENT_THRESHOLD = 1000.0
_WLM_VACANCY_CONFIDENCE = 0.35

_WLM_VACANCY_UPDATE = text(
    "UPDATE parcel SET "
    "is_vacant = (COALESCE(improvement_value, 0) < :threshold), "
    "vacancy_confidence = CASE WHEN COALESCE(improvement_value, 0) < :threshold "
    "THEN CAST(:conf AS numeric) ELSE NULL END "
    "WHERE market_code = :market"
)
_WLM_VACANT_COUNT = text("SELECT count(*) FROM parcel WHERE market_code = :market AND is_vacant")


async def derive_wlm_vacancy(session: AsyncSession) -> int:
    await session.execute(
        _WLM_VACANCY_UPDATE,
        {
            "market": _MARKET,
            "threshold": _VACANCY_IMPROVEMENT_THRESHOLD,
            "conf": _WLM_VACANCY_CONFIDENCE,
        },
    )
    count = await session.scalar(_WLM_VACANT_COUNT, {"market": _MARKET}) or 0
    await record_freshness(
        session,
        WLM_VACANCY_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=count,
    )
    return count
