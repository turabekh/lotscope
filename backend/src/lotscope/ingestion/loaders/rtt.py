from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.merge import merge_rtt
from lotscope.ingestion.models import IngestRun, StagingRtt
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.raw import write_raw
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.ingestion.vintage import vintage_from_dates
from lotscope.parcels.models import Parcel

RTT_DATASET = "rtt_summary"
RTT_KEY_COLUMN = "cartodb_id"
RTT_COLUMNS = (
    "cartodb_id",
    "document_id",
    "document_type",
    "recording_date",
    "opa_account_num",
    "street_address",
    "grantors",
    "grantees",
    "total_consideration",
)


class RttRecord(BaseModel):
    opa_account_num: str | int | None = None
    street_address: str | None = None
    document_id: str | int | None = None
    document_type: str | None = None
    recording_date: str | None = None
    grantors: str | None = None
    grantees: str | None = None
    total_consideration: float | None = None


def to_sale_row(record: RttRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.opa_account_num)
    document_id = str(record.document_id).strip() if record.document_id is not None else None
    if parcel_number is None or not document_id:
        return None
    return {
        "parcel_number": parcel_number,
        "document_id": document_id,
        "document_type": record.document_type,
        "sale_date": parse_iso_date(record.recording_date),
        "sale_price": record.total_consideration,
        "grantor": record.grantors,
        "grantee": record.grantees,
        "source": RTT_DATASET,
    }


def _staging_row(row: dict[str, Any], run_id: int) -> dict[str, Any]:
    return {
        "parcel_number": row["parcel_number"],
        "document_id": row["document_id"],
        "ingest_run_id": run_id,
        "document_type": row.get("document_type"),
        "sale_date": row.get("sale_date"),
        "sale_price": row.get("sale_price"),
        "grantor": row.get("grantor"),
        "grantee": row.get("grantee"),
        "source": row["source"],
    }


async def load_rtt(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    run = IngestRun(dataset=RTT_DATASET)
    session.add(run)
    await session.flush()
    await session.execute(text("DELETE FROM staging.rtt"))

    total = 0
    async for page in carto.paginate_by_key(
        table=RTT_DATASET,
        columns=RTT_COLUMNS,
        key_column=RTT_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        mapped: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for raw in page:
            row = to_sale_row(RttRecord.model_validate(raw))
            if row is None:
                continue
            mapped.append(row)
            raw_rows.append(
                {
                    "ingest_run_id": run.id,
                    "dataset": RTT_DATASET,
                    "natural_key": row["document_id"],
                    "payload": dict(raw),
                }
            )
        if not mapped:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": RTT_DATASET}
            for parcel_number in {row["parcel_number"] for row in mapped}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        staging_rows = [_staging_row(row, run.id) for row in mapped]
        await upsert(
            session, StagingRtt, staging_rows, index_elements=["parcel_number", "document_id"]
        )
        await write_raw(session, raw_rows)
        total += len(mapped)

    vintage = vintage_from_dates(
        (
            await session.execute(
                text("SELECT sale_date FROM staging.rtt WHERE ingest_run_id = :run_id"),
                {"run_id": run.id},
            )
        )
        .scalars()
        .all()
    )
    result = await merge_rtt(session, run.id)
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    run.raw_rows = total
    run.merged_rows = result.merged_rows
    run.event_count = result.event_count
    await session.flush()
    await record_freshness(
        session,
        RTT_DATASET,
        status="success",
        success=True,
        row_count=total,
        data_vintage=vintage,
    )
    return total
