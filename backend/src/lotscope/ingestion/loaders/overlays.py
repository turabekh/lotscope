import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.zoning.models import Rco, ZoningOverlay

_ARCGIS_ROOT = "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services"

ZONING_OVERLAY_DATASET = "zoning_overlays"
ZONING_OVERLAY_LAYER_URL = f"{_ARCGIS_ROOT}/Zoning_Overlays/FeatureServer/0/query"

RCO_DATASET = "zoning_rco"
RCO_LAYER_URL = f"{_ARCGIS_ROOT}/Zoning_RCO/FeatureServer/0/query"


def _geom_columns(feature: ArcGisFeature) -> dict[str, Any]:
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {"geom_4326": geom_4326, "geom_2272": func.ST_Transform(geom_4326, 2272)}


def to_overlay_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    external_id = first_present(props, "objectid", "OBJECTID")
    if feature.geometry is None or external_id is None:
        return None
    return {
        "external_id": str(external_id),
        "code": first_present(props, "overlay_symbol", "OVERLAY_SYMBOL"),
        "name": first_present(props, "overlay_name", "OVERLAY_NAME"),
        "code_section": first_present(props, "code_section", "CODE_SECTION"),
        "source": ZONING_OVERLAY_DATASET,
        **_geom_columns(feature),
    }


def to_rco_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    external_id = first_present(props, "objectid", "OBJECTID")
    if feature.geometry is None or external_id is None:
        return None
    return {
        "external_id": str(external_id),
        "name": first_present(props, "organization_name", "ORGANIZATION_NAME"),
        "org_type": first_present(props, "org_type", "ORG_TYPE"),
        "source": RCO_DATASET,
        **_geom_columns(feature),
    }


async def load_zoning_overlays(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = ZONING_OVERLAY_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [row for row in (to_overlay_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                ZoningOverlay,
                rows,
                index_elements=["external_id"],
                update_columns=["code", "name", "code_section", "geom_4326", "geom_2272", "source"],
            )
            total += len(rows)
    await record_freshness(
        session, ZONING_OVERLAY_DATASET, status="success", success=True, row_count=total
    )
    return total


async def load_rco(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = RCO_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [row for row in (to_rco_row(f) for f in features) if row is not None]
        if rows:
            await upsert(
                session,
                Rco,
                rows,
                index_elements=["external_id"],
                update_columns=["name", "org_type", "geom_4326", "geom_2272", "source"],
            )
            total += len(rows)
    await record_freshness(session, RCO_DATASET, status="success", success=True, row_count=total)
    return total
