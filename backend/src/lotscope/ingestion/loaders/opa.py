from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.merge import merge_opa
from lotscope.ingestion.models import IngestRun, StagingOpa
from lotscope.ingestion.raw import write_raw
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.verdict.cache import invalidate_after_ingest

OPA_DATASET = "opa_properties_public"
OPA_KEY_COLUMN = "parcel_number"
OPA_COLUMNS = (
    "parcel_number",
    "location",
    "zip_code",
    "owner_1",
    "mailing_address_1",
    "mailing_address_2",
    "mailing_street",
    "mailing_city_state",
    "mailing_zip",
    "category_code_description",
    "zoning",
    "market_value",
    "taxable_land",
    "taxable_building",
    "exempt_land",
    "exempt_building",
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
    mailing_address_2: str | None = None
    mailing_street: str | None = None
    mailing_city_state: str | None = None
    mailing_zip: str | None = None
    category_code_description: str | None = None
    zoning: str | None = None
    market_value: float | None = None
    taxable_land: float | None = None
    taxable_building: float | None = None
    exempt_land: float | None = None
    exempt_building: float | None = None
    total_area: float | None = None
    frontage: float | None = None
    depth: float | None = None


def mailing_address(record: OpaRecord) -> str | None:
    street = (record.mailing_street or record.mailing_address_1 or "").strip()
    if not street:
        return None
    tail = " ".join(
        part
        for part in ((record.mailing_city_state or "").strip(), (record.mailing_zip or "").strip())
        if part
    )
    return f"{street} {tail}".strip() if tail else street


def to_parcel_row(record: OpaRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.parcel_number)
    if parcel_number is None:
        return None
    return {
        "parcel_number": parcel_number,
        "address": record.location,
        "zip_code": record.zip_code,
        "owner": record.owner_1,
        "mailing_address": mailing_address(record),
        "land_use": record.category_code_description,
        "base_zoning_code": record.zoning,
        "market_value": record.market_value,
        "land_value": record.taxable_land,
        "improvement_value": record.taxable_building,
        "exempt_land": record.exempt_land,
        "exempt_building": record.exempt_building,
        "lot_area_sqft": record.total_area,
        "frontage_ft": record.frontage,
        "depth_ft": record.depth,
        "source": OPA_DATASET,
    }


def _staging_row(row: dict[str, Any], run_id: int) -> dict[str, Any]:
    staged = {key: value for key, value in row.items() if key != "source"}
    staged["ingest_run_id"] = run_id
    return staged


async def load_opa(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    run = IngestRun(dataset=OPA_DATASET)
    session.add(run)
    await session.flush()
    await session.execute(text("DELETE FROM staging.opa"))

    total = 0
    async for page in carto.paginate_by_key(
        table=OPA_DATASET,
        columns=OPA_COLUMNS,
        key_column=OPA_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        mapped: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for raw in page:
            row = to_parcel_row(OpaRecord.model_validate(raw))
            if row is None:
                continue
            mapped.append(row)
            raw_rows.append(
                {
                    "ingest_run_id": run.id,
                    "dataset": OPA_DATASET,
                    "natural_key": row["parcel_number"],
                    "payload": dict(raw),
                }
            )
        if not mapped:
            continue
        staging_rows = [_staging_row(row, run.id) for row in mapped]
        await upsert(session, StagingOpa, staging_rows, index_elements=["parcel_number"])
        await write_raw(session, raw_rows)
        total += len(mapped)

    result = await merge_opa(session, run.id, source=OPA_DATASET)
    await invalidate_after_ingest(result.touched)
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    run.raw_rows = total
    run.merged_rows = result.merged_rows
    run.event_count = result.event_count
    await session.flush()
    await record_freshness(session, OPA_DATASET, status="success", success=True, row_count=total)
    return total
