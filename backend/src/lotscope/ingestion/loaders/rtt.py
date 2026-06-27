from datetime import date
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.parcels.models import Parcel
from lotscope.valuation.models import Sale

RTT_DATASET = "rtt_summary"
RTT_KEY_COLUMN = "cartodb_id"
RTT_COLUMNS = (
    "cartodb_id",
    "document_id",
    "document_type",
    "recording_date",
    "opa_account_num",
    "grantors",
    "grantees",
    "total_consideration",
)


class RttRecord(BaseModel):
    opa_account_num: str | int | None = None
    document_id: str | int | None = None
    document_type: str | None = None
    recording_date: str | None = None
    grantors: str | None = None
    grantees: str | None = None
    total_consideration: float | None = None


def parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def to_sale_row(record: RttRecord) -> dict[str, Any] | None:
    parcel_number = normalize_account(record.opa_account_num)
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


async def load_rtt(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=RTT_DATASET,
        columns=RTT_COLUMNS,
        key_column=RTT_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        sales = [
            row
            for row in (to_sale_row(RttRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if not sales:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": RTT_DATASET}
            for parcel_number in {sale["parcel_number"] for sale in sales}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        await upsert(
            session, Sale, sales, index_elements=["parcel_number", "document_id"]
        )
        total += len(sales)
    await record_freshness(
        session, RTT_DATASET, status="success", success=True, row_count=total
    )
    return total
