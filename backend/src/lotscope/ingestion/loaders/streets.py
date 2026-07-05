import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.streets.models import StreetCenterline

STREETS_DATASET = "streets"
STREETS_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "Street_Centerline/FeatureServer/0/query"
)


def to_street_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    external_id = first_present(props, "seg_id", "objectid", "OBJECTID")
    if feature.geometry is None or external_id is None:
        return None
    street_name = first_present(props, "stname", "streetlabe", "st_name", "ST_NAME")
    street_class = first_present(props, "class", "CLASS")
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {
        "external_id": str(external_id),
        "street_name": str(street_name) if street_name is not None else None,
        "street_class": str(street_class) if street_class is not None else None,
        "geom_4326": geom_4326,
        "geom_local": func.ST_Transform(geom_4326, 2272),
        "source": STREETS_DATASET,
    }


async def load_streets(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = STREETS_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [row for row in (to_street_row(feature) for feature in features) if row is not None]
        if rows:
            await upsert(
                session,
                StreetCenterline,
                rows,
                index_elements=["external_id"],
                update_columns=["street_name", "street_class", "geom_4326", "geom_local", "source"],
            )
            total += len(rows)
    await record_freshness(
        session, STREETS_DATASET, status="success", success=True, row_count=total
    )
    return total
