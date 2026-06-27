from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.reconciliation import normalize_account
from lotscope.ingestion.service import record_freshness
from lotscope.ingestion.upsert import insert_ignore, upsert
from lotscope.parcels.models import Parcel
from lotscope.risk.models import TaxStatus

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


async def load_tax(
    session: AsyncSession,
    carto: CartoClient,
    *,
    page_size: int = 5000,
    where: str | None = None,
) -> int:
    total = 0
    async for page in carto.paginate_by_key(
        table=TAX_DATASET,
        columns=TAX_COLUMNS,
        key_column=TAX_KEY_COLUMN,
        page_size=page_size,
        where=where,
    ):
        rows = [
            row
            for row in (to_tax_row(TaxRecord.model_validate(raw)) for raw in page)
            if row is not None
        ]
        if not rows:
            continue
        parcel_stubs = [
            {"parcel_number": parcel_number, "source": TAX_DATASET}
            for parcel_number in {row["parcel_number"] for row in rows}
        ]
        await insert_ignore(session, Parcel, parcel_stubs, index_elements=["parcel_number"])
        await upsert(session, TaxStatus, rows, index_elements=["parcel_number"])
        total += len(rows)
    await record_freshness(session, TAX_DATASET, status="success", success=True, row_count=total)
    return total
