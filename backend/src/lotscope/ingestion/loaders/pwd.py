from typing import Any

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.reconciliation import normalize_account, normalize_pwd_id
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

PWD_DATASET = "pwd_parcels"
PWD_KEY_COLUMN = "cartodb_id"
PWD_COLUMNS = (
    "cartodb_id",
    "brt_number",
    "parcel_id",
    "ST_AsGeoJSON(the_geom) AS geom_geojson",
)


class PwdRecord(BaseModel):
    brt_number: str | int | None = None
    parcel_id: str | int | None = None
    geom_geojson: str | None = None


def to_parcel_geometry_row(record: PwdRecord) -> dict[str, Any] | None:
    parcel_number = normalize_account(record.brt_number)
    if parcel_number is None or not record.geom_geojson:
        return None
    geom_4326 = func.ST_SetSRID(func.ST_GeomFromGeoJSON(record.geom_geojson), 4326)
    return {
        "parcel_number": parcel_number,
        "pwd_parcel_id": normalize_pwd_id(record.parcel_id),
        "geom_4326": geom_4326,
        "geom_2272": func.ST_Transform(geom_4326, 2272),
        "source": PWD_DATASET,
    }


async def load_pwd(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 1000,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=PWD_DATASET,
        columns=PWD_COLUMNS,
        key_column=PWD_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (to_parcel_geometry_row(PwdRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if rows:
            await upsert(
                session,
                Parcel,
                rows,
                index_elements=["parcel_number"],
                update_columns=["pwd_parcel_id", "geom_4326", "geom_2272", "source"],
            )
            total += len(rows)
    await record_freshness(session, PWD_DATASET, status="success", success=True, row_count=total)
    return total
