from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.merge import merge_li
from lotscope.ingestion.models import IngestRun, StagingLiEvent
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.raw import write_raw
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.parcels.models import Parcel

LI_KEY_COLUMN = "cartodb_id"

LI_VIOLATIONS_DATASET = "violations"
LI_VIOLATIONS_COLUMNS = (
    "cartodb_id",
    "violationnumber",
    "opa_account_num",
    "violationcodetitle",
    "violationstatus",
    "violationdate",
)
LI_PERMITS_DATASET = "permits"
LI_PERMITS_COLUMNS = (
    "cartodb_id",
    "permitnumber",
    "opa_account_num",
    "permitdescription",
    "status",
    "permitissuedate",
)
LI_DEMOLITIONS_DATASET = "demolitions"
LI_DEMOLITIONS_COLUMNS = (
    "cartodb_id",
    "caseorpermitnumber",
    "opa_account_num",
    "status",
    "start_date",
)


class ViolationRecord(BaseModel):
    violationnumber: str | int | None = None
    opa_account_num: str | int | None = None
    violationcodetitle: str | None = None
    violationstatus: str | None = None
    violationdate: str | None = None


class PermitRecord(BaseModel):
    permitnumber: str | int | None = None
    opa_account_num: str | int | None = None
    permitdescription: str | None = None
    status: str | None = None
    permitissuedate: str | None = None


class DemolitionRecord(BaseModel):
    caseorpermitnumber: str | int | None = None
    opa_account_num: str | int | None = None
    status: str | None = None
    start_date: str | None = None


def _contains(text: str | None, needle: str) -> bool:
    return text is not None and needle in text.upper()


def _clean_id(value: str | int | None) -> str | None:
    return str(value).strip() if value is not None else None


def _base_event(
    parcel_number: str, external_id: str, event_type: str, source: str
) -> dict[str, Any]:
    return {
        "parcel_number": parcel_number,
        "external_id": external_id,
        "event_type": event_type,
        "source": source,
    }


def to_violation_event_row(record: ViolationRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.opa_account_num)
    external_id = _clean_id(record.violationnumber)
    if parcel_number is None or not external_id:
        return None
    return {
        **_base_event(parcel_number, external_id, "violation", LI_VIOLATIONS_DATASET),
        "status": record.violationstatus,
        "event_date": parse_iso_date(record.violationdate),
        "description": record.violationcodetitle,
        "is_unsafe": _contains(record.violationcodetitle, "UNSAFE"),
        "is_imminently_dangerous": _contains(record.violationcodetitle, "IMMINENTLY DANGEROUS"),
    }


def to_permit_event_row(record: PermitRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.opa_account_num)
    external_id = _clean_id(record.permitnumber)
    if parcel_number is None or not external_id:
        return None
    return {
        **_base_event(parcel_number, external_id, "permit", LI_PERMITS_DATASET),
        "status": record.status,
        "event_date": parse_iso_date(record.permitissuedate),
        "description": record.permitdescription,
    }


def to_demolition_event_row(record: DemolitionRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.opa_account_num)
    external_id = _clean_id(record.caseorpermitnumber)
    if parcel_number is None or not external_id:
        return None
    return {
        **_base_event(parcel_number, external_id, "demolition", LI_DEMOLITIONS_DATASET),
        "status": record.status,
        "event_date": parse_iso_date(record.start_date),
    }


def _staging_row(row: dict[str, Any], run_id: int, dataset: str) -> dict[str, Any]:
    return {
        "event_type": row["event_type"],
        "external_id": row["external_id"],
        "ingest_run_id": run_id,
        "parcel_number": row["parcel_number"],
        "status": row.get("status"),
        "event_date": row.get("event_date"),
        "description": row.get("description"),
        "is_unsafe": row.get("is_unsafe"),
        "is_imminently_dangerous": row.get("is_imminently_dangerous"),
        "source": dataset,
    }


async def _run_li_loader(
    session: AsyncSession,
    carto: CartoClient,
    *,
    dataset: str,
    event_type: str,
    columns: tuple[str, ...],
    record_model: type[BaseModel],
    row_factory: Callable[[Any], dict[str, Any] | None],
    page_size: int,
    where: str | None,
) -> int:
    run = IngestRun(dataset=dataset)
    session.add(run)
    await session.flush()
    await session.execute(
        text("DELETE FROM staging.li_event WHERE event_type = :event_type"),
        {"event_type": event_type},
    )

    total = 0
    async for page in carto.paginate_by_key(
        table=dataset,
        columns=columns,
        key_column=LI_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        mapped: list[dict[str, Any]] = []
        raw_rows: list[dict[str, Any]] = []
        for raw in page:
            row = row_factory(record_model.model_validate(raw))
            if row is None:
                continue
            mapped.append(row)
            raw_rows.append(
                {
                    "ingest_run_id": run.id,
                    "dataset": dataset,
                    "natural_key": row["external_id"],
                    "payload": dict(raw),
                }
            )
        if not mapped:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": dataset}
            for parcel_number in {row["parcel_number"] for row in mapped}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        staging_rows = [_staging_row(row, run.id, dataset) for row in mapped]
        await upsert(
            session, StagingLiEvent, staging_rows, index_elements=["event_type", "external_id"]
        )
        await write_raw(session, raw_rows)
        total += len(mapped)

    result = await merge_li(session, run.id, event_type)
    run.status = "success"
    run.finished_at = datetime.now(UTC)
    run.raw_rows = total
    run.merged_rows = result.merged_rows
    run.event_count = result.event_count
    await session.flush()
    await record_freshness(session, dataset, status="success", success=True, row_count=total)
    return total


async def load_li_violations(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    return await _run_li_loader(
        session,
        carto,
        dataset=LI_VIOLATIONS_DATASET,
        event_type="violation",
        columns=LI_VIOLATIONS_COLUMNS,
        record_model=ViolationRecord,
        row_factory=to_violation_event_row,
        page_size=page_size,
        where=where,
    )


async def load_li_permits(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    return await _run_li_loader(
        session,
        carto,
        dataset=LI_PERMITS_DATASET,
        event_type="permit",
        columns=LI_PERMITS_COLUMNS,
        record_model=PermitRecord,
        row_factory=to_permit_event_row,
        page_size=page_size,
        where=where,
    )


async def load_li_demolitions(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    return await _run_li_loader(
        session,
        carto,
        dataset=LI_DEMOLITIONS_DATASET,
        event_type="demolition",
        columns=LI_DEMOLITIONS_COLUMNS,
        record_model=DemolitionRecord,
        row_factory=to_demolition_event_row,
        page_size=page_size,
        where=where,
    )
