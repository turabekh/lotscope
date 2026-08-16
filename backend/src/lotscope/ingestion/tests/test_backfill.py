from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.backfill import (
    BackfillVerificationError,
    apply_mailing_updates,
    measure_mailing_coverage,
    recover_deeds,
    verify_no_loss,
)
from lotscope.ingestion.deed_recovery import RESOLVED, UNRESOLVED_COLLISION, UNRESOLVED_NO_MATCH

pytestmark = pytest.mark.integration


def _deed(document_id: str, address: str, price: float = 29100.0) -> dict[str, object]:
    return {
        "document_id": document_id,
        "street_address": address,
        "document_type": "SHERIFF'S DEED",
        "sale_date": date(2025, 5, 8),
        "sale_price": price,
        "grantor": "PRIOR OWNER",
        "grantee": "SHLAYEN RACHEL",
    }


async def _parcels(session: AsyncSession, rows: list[tuple[str, str]]) -> None:
    for parcel_number, address in rows:
        await session.execute(
            text(
                "INSERT INTO parcel (parcel_number, market_code, address) "
                "VALUES (:pn, 'phl', :addr)"
            ),
            {"pn": parcel_number, "addr": address},
        )
    await session.flush()


async def _sale_count(session: AsyncSession) -> int:
    return int((await session.execute(text("SELECT count(*) FROM sale"))).scalar_one())


async def test_a_recoverable_deed_lands_on_its_parcel(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900001", "2138 N FAIRHILL ST")])

    report = await recover_deeds(db_session, [_deed("D1", "2138 N. Fairhill St.")])

    assert report.applied == 1
    assert report.reasons[RESOLVED] == 1
    assert await _sale_count(db_session) == 1


async def test_a_dry_run_reports_without_writing(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900001", "2138 N FAIRHILL ST")])

    report = await recover_deeds(db_session, [_deed("D1", "2138 N FAIRHILL ST")], dry_run=True)

    assert report.staged == 1
    assert report.applied == 0
    assert await _sale_count(db_session) == 0


async def test_running_twice_changes_nothing_the_second_time(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900001", "2138 N FAIRHILL ST")])
    deeds = [_deed("D1", "2138 N FAIRHILL ST")]

    first = await recover_deeds(db_session, deeds)
    await db_session.flush()
    second = await recover_deeds(db_session, deeds)

    assert first.applied == 1
    assert second.applied == 1
    assert await _sale_count(db_session) == 1


async def test_a_partial_run_resumes_without_duplicating(db_session: AsyncSession) -> None:
    await _parcels(
        db_session, [("phl:900001", "2138 N FAIRHILL ST"), ("phl:900002", "1329 GROVE ST")]
    )

    await recover_deeds(db_session, [_deed("D1", "2138 N FAIRHILL ST")])
    await db_session.flush()
    await recover_deeds(
        db_session, [_deed("D1", "2138 N FAIRHILL ST"), _deed("D2", "1329 GROVE ST")]
    )

    assert await _sale_count(db_session) == 2


async def test_two_parcels_on_one_address_leave_the_deed_unattributed(
    db_session: AsyncSession,
) -> None:
    await _parcels(
        db_session, [("phl:900001", "50 SHARED ST"), ("phl:900002", "50 Shared Street")]
    )

    report = await recover_deeds(db_session, [_deed("D1", "50 SHARED ST")])

    assert report.applied == 0
    assert report.reasons[UNRESOLVED_COLLISION] == 1
    assert await _sale_count(db_session) == 0


async def test_an_unknown_address_is_counted_not_dropped_silently(
    db_session: AsyncSession,
) -> None:
    await _parcels(db_session, [("phl:900001", "2138 N FAIRHILL ST")])

    report = await recover_deeds(db_session, [_deed("D1", "999 NOWHERE AVE")])

    assert report.applied == 0
    assert report.reasons[UNRESOLVED_NO_MATCH] == 1
    assert report.scanned == 1


async def test_the_duplicate_document_collapses_on_its_key(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900002", "1329 GROVE ST")])
    duplicate = [_deed("SAME-DOC", "1329 GROVE ST"), _deed("SAME-DOC", "1329 Grove Street")]

    await recover_deeds(db_session, duplicate)

    assert await _sale_count(db_session) == 1


def test_a_shrinking_table_aborts_the_swap() -> None:
    verify_no_loss(before=1000, after=1000, label="sale")
    verify_no_loss(before=1000, after=1200, label="sale")

    with pytest.raises(BackfillVerificationError):
        verify_no_loss(before=1000, after=500, label="sale")


def test_verification_tolerates_an_empty_starting_table() -> None:
    verify_no_loss(before=0, after=0, label="sale")


async def test_the_mailing_backfill_fills_addresses_and_reports_coverage(
    db_session: AsyncSession,
) -> None:
    await _parcels(db_session, [("phl:900010", "1 A ST"), ("phl:900011", "2 B ST")])

    before = await measure_mailing_coverage(db_session)
    report = await apply_mailing_updates(
        db_session,
        [
            {"parcel_number": "phl:900010", "mailing_address": "8319 CHILDS RD WYNDMOOR PA 19038"},
            {"parcel_number": "phl:900011", "mailing_address": None},
        ],
    )
    after = await measure_mailing_coverage(db_session)

    assert report.applied == 1
    assert before.with_mailing == 0
    assert after.with_mailing == 1


async def test_the_mailing_dry_run_writes_nothing(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900012", "3 C ST")])

    report = await apply_mailing_updates(
        db_session,
        [{"parcel_number": "phl:900012", "mailing_address": "8319 CHILDS RD"}],
        dry_run=True,
    )

    assert report.staged == 1
    assert report.applied == 0
    assert (await measure_mailing_coverage(db_session)).with_mailing == 0


async def test_rerunning_the_mailing_backfill_is_idempotent(db_session: AsyncSession) -> None:
    await _parcels(db_session, [("phl:900013", "4 D ST")])
    updates: list[dict[str, object]] = [
        {"parcel_number": "phl:900013", "mailing_address": "8319 CHILDS RD"}
    ]

    await apply_mailing_updates(db_session, updates)
    await db_session.flush()
    await apply_mailing_updates(db_session, updates)

    assert (await measure_mailing_coverage(db_session)).with_mailing == 1
