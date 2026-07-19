import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.errors import IngestionError
from lotscope.ingestion.normalizers import get_normalizer
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

WLM_PARCELS_DATASET = "firstmap_parcels"
WLM_ASSESSMENT_DATASET = "wilmington_assessment"
_MARKET = "wlm"
_LOCAL_SRID = 2235

_WILMINGTON_PARCELS_LAYER = "LUP_Map_w_RISE_STAR_Bldg_Code_Enf_and_DDD_WFL1/FeatureServer/0"
_ASSESSMENT_FIELDS = "PRCLID,OWNER,OWNRADD1,OWNRADD2,ASMTLAND,ASMTSTRT,PROP_CLASS"

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
