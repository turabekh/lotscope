from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.parcels.models import Parcel

OPA_DATASET = "opa_properties_public"
OPA_KEY_COLUMN = "parcel_number"
OPA_COLUMNS = (
    "parcel_number",
    "location",
    "zip_code",
    "owner_1",
    "mailing_address_1",
    "category_code_description",
    "zoning",
    "market_value",
    "taxable_land",
    "taxable_building",
    "total_area",
    "frontage",
    "depth",
)


class OpaRecord(BaseModel):
    parcel_number: str | None = None
    location: str | None = None
    zip_code: str | None = None
    owner_1: str | None = None
    mailing_address_1: str | None = None
    category_code_description: str | None = None
    zoning: str | None = None
    market_value: float | None = None
    taxable_land: float | None = None
    taxable_building: float | None = None
    total_area: float | None = None
    frontage: float | None = None
    depth: float | None = None


def to_parcel_row(record: OpaRecord) -> dict[str, Any] | None:
    parcel_number = normalize_account(record.parcel_number)
    if parcel_number is None:
        return None
    return {
        "parcel_number": parcel_number,
        "address": record.location,
        "zip_code": record.zip_code,
        "owner": record.owner_1,
        "mailing_address": record.mailing_address_1,
        "land_use": record.category_code_description,
        "base_zoning_code": record.zoning,
        "market_value": record.market_value,
        "land_value": record.taxable_land,
        "improvement_value": record.taxable_building,
        "lot_area_sqft": record.total_area,
        "frontage_ft": record.frontage,
        "depth_ft": record.depth,
        "source": OPA_DATASET,
    }


async def load_opa(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=OPA_DATASET,
        columns=OPA_COLUMNS,
        key_column=OPA_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (to_parcel_row(OpaRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if rows:
            await upsert(session, Parcel, rows, index_elements=["parcel_number"])
            total += len(rows)
    await record_freshness(session, OPA_DATASET, status="success", success=True, row_count=total)
    return total
