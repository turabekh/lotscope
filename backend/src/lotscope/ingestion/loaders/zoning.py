import json
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.parsing import first_present
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.zoning.models import ZoningDistrict

ZONING_DATASET = "zoning_base_districts"
ZONING_LAYER_URL = (
    "https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
    "Zoning_BaseDistricts/FeatureServer/0/query"
)


def to_zoning_row(feature: ArcGisFeature) -> dict[str, Any] | None:
    props = feature.properties
    external_id = first_present(props, "OBJECTID", "objectid")
    code = first_present(props, "CODE", "code", "LONG_CODE", "long_code")
    if feature.geometry is None or external_id is None or code is None:
        return None
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(feature.geometry)), 4326)
    return {
        "external_id": str(external_id),
        "code": str(code),
        "long_code": first_present(props, "LONG_CODE", "long_code"),
        "geom_4326": geom_4326,
        "geom_2272": func.ST_Transform(geom_4326, 2272),
        "source": ZONING_DATASET,
    }


async def load_zoning_districts(
    session: AsyncSession,
    arcgis: ArcGisClient,
    *,
    layer_url: str = ZONING_LAYER_URL,
    page_size: int = 2000,
    where: str = "1=1",
) -> int:
    total = 0
    async for features in arcgis.paginate(layer_url, where=where, page_size=page_size):
        rows = [row for row in (to_zoning_row(feature) for feature in features) if row is not None]
        if rows:
            await upsert(
                session,
                ZoningDistrict,
                rows,
                index_elements=["external_id"],
                update_columns=["code", "long_code", "geom_4326", "geom_2272", "source"],
            )
            total += len(rows)
    await record_freshness(session, ZONING_DATASET, status="success", success=True, row_count=total)
    return total
