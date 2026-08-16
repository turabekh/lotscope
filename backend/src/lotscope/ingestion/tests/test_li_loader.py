from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.li import ViolationRecord, to_violation_event_row
from lotscope.ingestion.models import DatasetFreshness


def test_to_violation_event_row_maps_and_flags() -> None:
    row = to_violation_event_row(
        ViolationRecord(
            violationnumber=987,
            opa_account_num="1234567",
            violationcodetitle="UNSAFE STRUCTURE",
            violationstatus="OPEN",
            violationdate="2023-07-04",
        )
    )
    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["external_id"] == "987"
    assert row["event_type"] == "violation"
    assert row["is_unsafe"] is True
    assert row["is_imminently_dangerous"] is False


def test_to_violation_event_row_skips_without_key_or_id() -> None:
    assert (
        to_violation_event_row(ViolationRecord(opa_account_num=None, violationnumber="1")) is None
    )
    assert (
        to_violation_event_row(ViolationRecord(opa_account_num="1234567", violationnumber=None))
        is None
    )


class _RowsHandler:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        index = min(self.calls, len(self._pages) - 1)
        self.calls += 1
        return httpx.Response(200, json={"rows": self._pages[index]})


def _settings() -> Settings:
    return Settings(_env_file=None, carto_sql_url="http://carto.test/sql", http_backoff_seconds=0.0)


def _violation(cartodb_id: int, number: str) -> dict[str, Any]:
    return {
        "cartodb_id": cartodb_id,
        "violationnumber": number,
        "opa_account_num": "1234567",
        "violationcodetitle": "IMMINENTLY DANGEROUS",
        "violationstatus": "OPEN",
        "violationdate": "2023-01-01",
    }


@pytest.mark.integration
async def test_load_li_violations_inserts_event(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.li import load_li_violations

    handler = _RowsHandler([[_violation(1, "V-1")]])
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        total = await load_li_violations(db_session, carto, page_size=500)
    await db_session.flush()

    assert total == 1
    event = (
        await db_session.execute(
            text(
                "SELECT event_type, is_imminently_dangerous FROM li_event WHERE external_id = 'V-1'"
            )
        )
    ).one()
    assert event[0] == "violation"
    assert event[1] is True

    fresh = await db_session.get(DatasetFreshness, ("phl", "violations"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_li_violations_is_idempotent(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.li import load_li_violations

    pages = [[_violation(1, "V-9")]]
    for _ in range(2):
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_li_violations(db_session, carto, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(text("SELECT count(*) FROM li_event WHERE external_id = 'V-9'"))
    assert count == 1


@pytest.mark.integration
async def test_load_li_violations_emits_event_for_new_row_on_second_run(
    db_session: AsyncSession,
) -> None:
    from lotscope.ingestion.loaders.li import load_li_violations

    runs = [[[_violation(1, "V-9")]], [[_violation(1, "V-9"), _violation(2, "V-10")]]]
    for pages in runs:
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_li_violations(db_session, carto, page_size=500)
        await db_session.flush()

    events = (
        await db_session.execute(
            text("SELECT code, new_value->>'external_id' AS ext FROM parcel_event ORDER BY id")
        )
    ).all()
    assert [(e.code, e.ext) for e in events] == [("danger", "V-10")]


def test_violation_event_carries_the_case_status_alongside_the_violation_status() -> None:
    event = to_violation_event_row(
        ViolationRecord(
            violationnumber="VI-2025-044445",
            opa_account_num="201133900",
            violationcodetitle="VACANT STRUCTURE & LAND",
            violationstatus="COMPLIED",
            casestatus="CLOSED",
            violationdate="2025-06-16",
        )
    )

    assert event is not None
    assert event["status"] == "COMPLIED"
    assert event["case_status"] == "CLOSED"


async def test_case_status_survives_staging_and_the_merge(db_session: AsyncSession) -> None:
    from lotscope.ingestion.merge import merge_li
    from lotscope.ingestion.models import IngestRun, StagingLiEvent
    from lotscope.ingestion.upsert import upsert

    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES ('phl:cs1', 'phl')")
    )
    run = IngestRun(dataset="violations")
    db_session.add(run)
    await db_session.flush()

    row = to_violation_event_row(
        ViolationRecord(
            violationnumber="VI-CS-1",
            opa_account_num="cs1",
            violationcodetitle="VACANT STRUCTURE & LAND",
            violationstatus="COMPLIED",
            casestatus="IN VIOLATION",
            violationdate="2025-06-16",
        )
    )
    assert row is not None
    staged = {k: v for k, v in row.items() if k != "source"}
    staged["ingest_run_id"] = run.id
    staged["parcel_number"] = "phl:cs1"
    await upsert(db_session, StagingLiEvent, [staged], index_elements=["event_type", "external_id"])
    await merge_li(db_session, run.id, "violation")
    await db_session.flush()

    stored = (
        await db_session.execute(
            text(
                "SELECT status, case_status FROM li_event "
                "WHERE event_type='violation' AND external_id='VI-CS-1'"
            )
        )
    ).one()

    assert stored.status == "COMPLIED"
    assert stored.case_status == "IN VIOLATION"
