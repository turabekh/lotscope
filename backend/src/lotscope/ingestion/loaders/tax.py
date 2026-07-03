from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.merge import merge_tax
from lotscope.ingestion.models import IngestRun, RawRecord, StagingTax
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import batch_by_bind_limit, insert_ignore, upsert
from lotscope.parcels.models import Parcel

TAX_DATASET = "real_estate_tax_delinquencies"
TAX_KEY_COLUMN = "cartodb_id"
TAX_COLUMNS = (
    "cartodb_id",
    "opa_number",
    "total_due",
    "principal_due",
    "num_years_owed",
)


class TaxRecord(BaseModel):
    opa_number: str | int | None = None
    total_due: float | None = None
    principal_due: float | None = None
    num_years_owed: int | None = None


def to_tax_row(record: TaxRecord) -> dict[str, Any] | None:
    parcel_number = normalize_account(record.opa_number)
    if parcel_number is None:
        return None
    return {
        "parcel_number": parcel_number,
        "total_due": record.total_due,
        "principal_due": record.principal_due,
        "years_owed": record.num_years_owed,
        "is_delinquent": (record.total_due or 0) > 0,
        "source": TAX_DATASET,
    }


async def _write_raw(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> None:
    for batch in batch_by_bind_limit(rows):
        await session.execute(pg_insert(RawRecord).values(list(batch)))


async def load_tax(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    run = IngestRun(dataset=TAX_DATASET)
    session.add(run)
    await session.flush()
    await session.execute(text("DELETE FROM staging.tax"))

    total = 0
    async for page in carto.paginate_by_key(
        table=TAX_DATASET,
        columns=TAX_COLUMNS,
        key_column=TAX_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        mapped: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for raw in page:
            row = to_tax_row(TaxRecord.model_validate(raw))
            if row is None:
                continue
            mapped.append(row)
            raw_rows.append(
                {
                    "ingest_run_id": run.id,
                    "dataset": TAX_DATASET,
                    "natural_key": row["parcel_number"],
                    "payload": dict(raw),
                }
            )
        if not mapped:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": TAX_DATASET}
            for parcel_number in {row["parcel_number"] for row in mapped}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        staging_rows = [
            {
                "parcel_number": row["parcel_number"],
                "ingest_run_id": run.id,
                "is_delinquent": row["is_delinquent"],
                "total_due": row["total_due"],
                "principal_due": row["principal_due"],
                "years_owed": row["years_owed"],
            }
            for row in mapped
        ]
        await upsert(session, StagingTax, staging_rows, index_elements=["parcel_number"])
        await _write_raw(session, raw_rows)
        total += len(mapped)

    result = await merge_tax(session, run.id)
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    run.raw_rows = total
    run.merged_rows = result.merged_rows
    run.event_count = result.event_count
    await session.flush()
    await record_freshness(session, TAX_DATASET, status="success", success=True, row_count=total)
    return total
