from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import LiEvent

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
    parcel_number = normalize_account(record.opa_account_num)
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
    parcel_number = normalize_account(record.opa_account_num)
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
    parcel_number = normalize_account(record.opa_account_num)
    external_id = _clean_id(record.caseorpermitnumber)
    if parcel_number is None or not external_id:
        return None
    return {
        **_base_event(parcel_number, external_id, "demolition", LI_DEMOLITIONS_DATASET),
        "status": record.status,
        "event_date": parse_iso_date(record.start_date),
    }


async def _run_li_loader(
    session: AsyncSession,
    carto: CartoClient,
    *,
    dataset: str,
    columns: tuple[str, ...],
    record_model: type[BaseModel],
    row_factory: Callable[[Any], dict[str, Any] | None],
    page_size: int,
    where: str | None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=dataset,
        columns=columns,
        key_column=LI_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (row_factory(record_model.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if not rows:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": dataset}
            for parcel_number in {row["parcel_number"] for row in rows}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        await upsert(session, LiEvent, rows, index_elements=["event_type", "external_id"])
        total += len(rows)
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
        columns=LI_DEMOLITIONS_COLUMNS,
        record_model=DemolitionRecord,
        row_factory=to_demolition_event_row,
        page_size=page_size,
        where=where,
    )
