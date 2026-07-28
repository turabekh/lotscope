import asyncio
import csv
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.logging import get_logger
from lotscope.ingestion.merge import merge_sheriff
from lotscope.ingestion.models import IngestRun, StagingSheriffSale
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.raw import write_raw
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.parcels.models import Parcel

SHERIFF_DATASET = "sheriff_sale"

_logger = get_logger("ingestion.sheriff")


class SheriffSource(Protocol):
    async def fetch(self) -> list[dict[str, Any]]: ...


class CsvSheriffSource:
    def __init__(self, path: str) -> None:
        self._path = path

    def _read(self) -> list[dict[str, Any]]:
        with open(self._path, newline="", encoding="utf-8") as handle:
            return [dict(row) for row in csv.DictReader(handle)]

    async def fetch(self) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._read)


class SheriffSaleRecord(BaseModel):
    case_number: str | None = None
    opa_number: str | int | None = None
    parcel_number: str | None = None
    address: str | None = None
    sale_type: str | None = None
    status: str | None = None
    sale_date: str | None = None
    opening_bid: float | None = None
    plaintiff: str | None = None


def to_sheriff_row(record: SheriffSaleRecord) -> dict[str, Any] | None:
    parcel_number = record.parcel_number or to_parcel_key(record.opa_number)
    case_number = record.case_number.strip() if record.case_number else None
    if parcel_number is None or not case_number:
        return None
    return {
        "parcel_number": parcel_number,
        "case_number": case_number,
        "sale_type": record.sale_type,
        "status": record.status,
        "sale_date": parse_iso_date(record.sale_date),
        "opening_bid": record.opening_bid,
        "plaintiff": record.plaintiff,
        "source": SHERIFF_DATASET,
    }


def _staging_row(row: dict[str, Any], run_id: int) -> dict[str, Any]:
    return {
        "case_number": row["case_number"],
        "ingest_run_id": run_id,
        "parcel_number": row["parcel_number"],
        "sale_type": row.get("sale_type"),
        "sale_date": row.get("sale_date"),
        "status": row.get("status"),
        "opening_bid": row.get("opening_bid"),
        "plaintiff": row.get("plaintiff"),
        "source": row["source"],
    }


def _skip_detail(fetched: int, unidentified: int, out_of_market: int) -> str | None:
    parts = []
    if out_of_market:
        parts.append(f"{out_of_market} outside this market")
    if unidentified:
        parts.append(f"{unidentified} without a parcel id")
    if not parts:
        return None
    return f"{unidentified + out_of_market} of {fetched} rows skipped: " + ", ".join(parts)


async def load_sheriff(
    session: AsyncSession,
    source: SheriffSource,
    *,
    market_code: str = "phl",
    known_parcels: set[str] | None = None,
) -> int:
    run = IngestRun(dataset=SHERIFF_DATASET)
    session.add(run)
    await session.flush()
    await session.execute(text("DELETE FROM staging.sheriff_sale"))

    fetched = await source.fetch()
    mapped: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    unidentified = 0
    out_of_market = 0
    for raw in fetched:
        row = to_sheriff_row(SheriffSaleRecord.model_validate(raw))
        if row is None:
            unidentified += 1
            continue
        if known_parcels is not None and row["parcel_number"] not in known_parcels:
            out_of_market += 1
            continue
        mapped.append(row)
        raw_rows.append(
            {
                "ingest_run_id": run.id,
                "dataset": SHERIFF_DATASET,
                "natural_key": row["case_number"],
                "payload": dict(raw),
            }
        )

    total = len(mapped)
    skipped = unidentified + out_of_market
    if mapped:
        if known_parcels is None:
            parcel_stubs = [
                {"parcel_number": parcel_number, "source": SHERIFF_DATASET}
                for parcel_number in {row["parcel_number"] for row in mapped}
            ]
            await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        staging_rows = [_staging_row(row, run.id) for row in mapped]
        await upsert(session, StagingSheriffSale, staging_rows, index_elements=["case_number"])
        await write_raw(session, raw_rows)

    result = await merge_sheriff(session, run.id)
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    run.raw_rows = total
    run.merged_rows = result.merged_rows
    run.event_count = result.event_count
    await session.flush()
    _logger.info(
        "sheriff_load_complete",
        fetched=len(fetched),
        kept=total,
        skipped=skipped,
        unidentified=unidentified,
        out_of_market=out_of_market,
    )
    detail = _skip_detail(len(fetched), unidentified, out_of_market)
    await record_freshness(
        session,
        SHERIFF_DATASET,
        status="success",
        success=True,
        market_code=market_code,
        row_count=total,
        detail=detail,
    )
    return total
