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

LI_VIOLATIONS_DATASET = "violations"
LI_KEY_COLUMN = "cartodb_id"
LI_VIOLATIONS_COLUMNS = (
    "cartodb_id",
    "violationnumber",
    "opa_account_num",
    "violationcodetitle",
    "violationstatus",
    "violationdate",
)
VIOLATION_EVENT_TYPE = "violation"


class ViolationRecord(BaseModel):
    violationnumber: str | int | None = None
    opa_account_num: str | int | None = None
    violationcodetitle: str | None = None
    violationstatus: str | None = None
    violationdate: str | None = None


def _contains(text: str | None, needle: str) -> bool:
    return text is not None and needle in text.upper()


def to_violation_event_row(record: ViolationRecord) -> dict[str, Any] | None:
    parcel_number = normalize_account(record.opa_account_num)
    external_id = (
        str(record.violationnumber).strip() if record.violationnumber is not None else None
    )
    if parcel_number is None or not external_id:
        return None
    return {
        "parcel_number": parcel_number,
        "external_id": external_id,
        "event_type": VIOLATION_EVENT_TYPE,
        "status": record.violationstatus,
        "event_date": parse_iso_date(record.violationdate),
        "description": record.violationcodetitle,
        "is_unsafe": _contains(record.violationcodetitle, "UNSAFE"),
        "is_imminently_dangerous": _contains(record.violationcodetitle, "IMMINENTLY DANGEROUS"),
        "source": LI_VIOLATIONS_DATASET,
    }


async def load_li_violations(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=LI_VIOLATIONS_DATASET,
        columns=LI_VIOLATIONS_COLUMNS,
        key_column=LI_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (
                to_violation_event_row(ViolationRecord.model_validate(raw)) for raw in page
            )
            if row is not None
        ]
        if not rows:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": LI_VIOLATIONS_DATASET}
            for parcel_number in {row["parcel_number"] for row in rows}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        await upsert(session, LiEvent, rows, index_elements=["event_type", "external_id"])
        total += len(rows)
    await record_freshness(
        session, LI_VIOLATIONS_DATASET, status="success", success=True, row_count=total
    )
    return total
