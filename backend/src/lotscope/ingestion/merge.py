from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.events import TaxSnapshot, diff_tax
from lotscope.ingestion.models import ParcelEvent

TAX_DATASET = "tax_delinquency"

_STAGING_JOIN_SQL = text(
    "SELECT s.parcel_number, "
    "s.is_delinquent AS s_delinquent, s.total_due AS s_total_due, "
    "s.in_sheriff_sale AS s_sheriff, "
    "c.is_delinquent AS c_delinquent, c.total_due AS c_total_due, "
    "c.in_sheriff_sale AS c_sheriff, "
    "(c.parcel_number IS NOT NULL) AS has_core "
    "FROM staging.tax s "
    "LEFT JOIN tax_status c ON c.parcel_number = s.parcel_number "
    "WHERE s.ingest_run_id = :ingest_run_id"
)

_UPSERT_CORE_SQL = text(
    "INSERT INTO tax_status "
    "(parcel_number, is_delinquent, total_due, principal_due, years_owed, "
    "lien_count, in_sheriff_sale, as_of_date, updated_at) "
    "SELECT parcel_number, is_delinquent, total_due, principal_due, years_owed, "
    "lien_count, in_sheriff_sale, as_of_date, now() "
    "FROM staging.tax WHERE ingest_run_id = :ingest_run_id "
    "ON CONFLICT (parcel_number) DO UPDATE SET "
    "is_delinquent = excluded.is_delinquent, total_due = excluded.total_due, "
    "principal_due = excluded.principal_due, years_owed = excluded.years_owed, "
    "lien_count = excluded.lien_count, in_sheriff_sale = excluded.in_sheriff_sale, "
    "as_of_date = excluded.as_of_date, updated_at = now()"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


@dataclass(frozen=True)
class MergeResult:
    merged_rows: int
    event_count: int


async def merge_tax(session: AsyncSession, ingest_run_id: int) -> MergeResult:
    rows = (await session.execute(_STAGING_JOIN_SQL, {"ingest_run_id": ingest_run_id})).all()

    events = 0
    for row in rows:
        old = (
            TaxSnapshot(
                is_delinquent=row.c_delinquent,
                total_due=_as_float(row.c_total_due),
                in_sheriff_sale=row.c_sheriff,
            )
            if row.has_core
            else None
        )
        new = TaxSnapshot(
            is_delinquent=row.s_delinquent,
            total_due=_as_float(row.s_total_due),
            in_sheriff_sale=row.s_sheriff,
        )
        for draft in diff_tax(old, new):
            session.add(
                ParcelEvent(
                    parcel_number=row.parcel_number,
                    dataset=TAX_DATASET,
                    code=draft.code,
                    severity=draft.severity,
                    old_value=draft.old_value,
                    new_value=draft.new_value,
                    ingest_run_id=ingest_run_id,
                )
            )
            events += 1

    await session.flush()
    await session.execute(_UPSERT_CORE_SQL, {"ingest_run_id": ingest_run_id})
    return MergeResult(merged_rows=len(rows), event_count=events)
