import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.merge import merge_tax

pytestmark = pytest.mark.integration


async def _add_run(session: AsyncSession, run_id: int) -> None:
    await session.execute(
        text("INSERT INTO ingest_run (id, dataset) VALUES (:id, 'tax_delinquency')"),
        {"id": run_id},
    )


async def _add_parcel(session: AsyncSession, parcel_number: str) -> None:
    await session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES (:pn, 'OWNER')"),
        {"pn": parcel_number},
    )


async def _add_core_tax(
    session: AsyncSession, parcel_number: str, *, delinquent: bool, due: float, sheriff: bool
) -> None:
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, in_sheriff_sale) "
            "VALUES (:pn, :d, :due, :s)"
        ),
        {"pn": parcel_number, "d": delinquent, "due": due, "s": sheriff},
    )


async def _add_staging(
    session: AsyncSession,
    parcel_number: str,
    run_id: int,
    *,
    delinquent: bool,
    due: float,
    sheriff: bool,
) -> None:
    await session.execute(
        text(
            "INSERT INTO staging.tax (parcel_number, ingest_run_id, is_delinquent, total_due, "
            "in_sheriff_sale) VALUES (:pn, :run, :d, :due, :s)"
        ),
        {"pn": parcel_number, "run": run_id, "d": delinquent, "due": due, "s": sheriff},
    )


async def _events(session: AsyncSession, parcel_number: str) -> list[str]:
    rows = (
        await session.execute(
            text("SELECT code FROM parcel_event WHERE parcel_number = :pn ORDER BY code"),
            {"pn": parcel_number},
        )
    ).all()
    return [row[0] for row in rows]


async def test_merge_emits_events_for_changes_and_upserts_core(db_session: AsyncSession) -> None:
    await _add_run(db_session, 1)
    await _add_parcel(db_session, "000000001")
    await _add_core_tax(db_session, "000000001", delinquent=False, due=1000, sheriff=False)
    await _add_staging(db_session, "000000001", 1, delinquent=True, due=5000, sheriff=False)
    await db_session.flush()

    result = await merge_tax(db_session, 1)
    assert result.merged_rows == 1
    assert result.event_count == 2
    assert await _events(db_session, "000000001") == ["delinquent", "tax_up"]

    due = await db_session.scalar(
        text("SELECT total_due FROM tax_status WHERE parcel_number = '000000001'")
    )
    assert float(due) == 5000


async def test_merge_first_time_row_emits_no_events(db_session: AsyncSession) -> None:
    await _add_run(db_session, 7)
    await _add_parcel(db_session, "000000002")
    await _add_staging(db_session, "000000002", 7, delinquent=True, due=9000, sheriff=True)
    await db_session.flush()

    result = await merge_tax(db_session, 7)
    assert result.merged_rows == 1
    assert result.event_count == 0
    assert await _events(db_session, "000000002") == []
    exists = await db_session.scalar(
        text("SELECT count(*) FROM tax_status WHERE parcel_number = '000000002'")
    )
    assert exists == 1
