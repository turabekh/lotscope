from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.ingestion.reconciliation import to_parcel_key
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import upsert
from lotscope.zba.models import ZbaAppeal

ZBA_DATASET = "appeals"
ZBA_KEY_COLUMN = "cartodb_id"
ZBA_COLUMNS = (
    "cartodb_id",
    "appealnumber",
    "opa_account_num",
    "applicationtype",
    "decision",
    "decisiondate",
    "scheduleddate",
    "address",
)


class ZbaRecord(BaseModel):
    appealnumber: str | int | None = None
    opa_account_num: str | int | None = None
    applicationtype: str | None = None
    decision: str | None = None
    decisiondate: str | None = None
    scheduleddate: str | None = None
    address: str | None = None


def to_zba_row(record: ZbaRecord) -> dict[str, Any] | None:
    appeal_number = str(record.appealnumber).strip() if record.appealnumber is not None else None
    if not appeal_number:
        return None
    return {
        "appeal_number": appeal_number,
        "parcel_number": to_parcel_key(record.opa_account_num),
        "appeal_type": record.applicationtype,
        "decision": record.decision,
        "decision_date": parse_iso_date(record.decisiondate)
        or parse_iso_date(record.scheduleddate),
        "address": record.address,
        "source": ZBA_DATASET,
    }


async def load_zba(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 500,
    where: str | None = None,
) -> int:
    total = 0
    unresolved = 0
    async for page in carto.paginate_by_key(
        table=ZBA_DATASET,
        columns=ZBA_COLUMNS,
        key_column=ZBA_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (to_zba_row(ZbaRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        unresolved += sum(1 for row in rows if row["parcel_number"] is None)
        if rows:
            await upsert(
                session,
                ZbaAppeal,
                rows,
                index_elements=["appeal_number"],
                update_columns=[
                    "parcel_number",
                    "appeal_type",
                    "decision",
                    "decision_date",
                    "address",
                    "source",
                ],
            )
            total += len(rows)
    await record_freshness(
        session,
        ZBA_DATASET,
        status="success",
        success=True,
        row_count=total,
        detail=f"{unresolved} appeal(s) without a resolvable parcel key",
    )
    return total
