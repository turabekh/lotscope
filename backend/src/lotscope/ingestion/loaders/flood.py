import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.risk.models import FloodZone

FLOOD_DATASET = "fema_flood"
FLOOD_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "FEMA_Flood_Hazard_Areas/FeatureServer/0/query"
)


def to_flood_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    external_id = first_present(props, "OBJECTID", "objectid", "FID")
    if feature.geometry is None or external_id is None:
        return None
    zone = first_present(props, "FLD_ZONE", "fld_zone", "ZONE", "zone")
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {
        "external_id": str(external_id),
        "zone": str(zone) if zone is not None else None,
        "geom_4326": geom_4326,
        "geom_2272": func.ST_Transform(geom_4326, 2272),
        "source": FLOOD_DATASET,
    }


async def load_flood(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = FLOOD_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [
            row for row in (to_flood_row(feature) for feature in features) if row is not None
        ]
        if rows:
            await upsert(
                session,
                FloodZone,
                rows,
                index_elements=["external_id"],
                update_columns=["zone", "geom_4326", "geom_2272", "source"],
            )
            total += len(rows)
    await record_freshness(
        session, FLOOD_DATASET, status="success", success=True, row_count=total
    )
    return total
