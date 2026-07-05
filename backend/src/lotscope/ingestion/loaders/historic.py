from typing import Any

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.historic.models import HistoricDistrict
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert

HISTORIC_DATASET = "historicdistricts_local"
HISTORIC_KEY_COLUMN = "cartodb_id"
HISTORIC_COLUMNS = (
    "cartodb_id",
    "objectid",
    "name",
    "designated",
    "ST_AsGeoJSON(the_geom) AS geom_geojson",
)


class HistoricRecord(BaseModel):
    objectid: int | str | None = None
    name: str | None = None
    designated: str | None = None
    geom_geojson: str | None = None


def to_historic_row(record: HistoricRecord) -> dict[str, Any] | None:
    if not record.geom_geojson or record.objectid is None:
        return None
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(record.geom_geojson), 4326)
    return {
        "external_id": str(record.objectid),
        "name": record.name,
        "designated_date": parse_iso_date(record.designated),
        "geom_4326": geom_4326,
        "geom_local": func.ST_Transform(geom_4326, 2272),
        "source": HISTORIC_DATASET,
    }


async def load_historic(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 500,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=HISTORIC_DATASET,
        columns=HISTORIC_COLUMNS,
        key_column=HISTORIC_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (to_historic_row(HistoricRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if rows:
            await upsert(
                session,
                HistoricDistrict,
                rows,
                index_elements=["external_id"],
                update_columns=["name", "designated_date", "geom_4326", "geom_local", "source"],
            )
            total += len(rows)
    await record_freshness(
        session, HISTORIC_DATASET, status="success", success=True, row_count=total
    )
    return total
