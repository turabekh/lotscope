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
_MARKET = "wlm"
_LOCAL_SRID = 2235

_PARCEL_UPDATE_COLUMNS = [
    "coverage",
    "lot_area_sqft",
    "lot_area_source",
    "geom_local",
    "geom_4326",
]


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
