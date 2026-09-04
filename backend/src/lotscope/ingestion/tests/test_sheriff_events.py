from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.loaders.sheriff import load_sheriff
from lotscope.search.spatial import build_filters

pytestmark = pytest.mark.integration

_FUTURE = date.today() + timedelta(days=30)
_LATER = date.today() + timedelta(days=60)


class _FakeSource:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetch(self) -> list[dict[str, Any]]:
        return list(self._rows)


def _row(case: str, opa: str, sale_date: date, status: str) -> dict[str, Any]:
    return {
        "case_number": case,
        "opa_number": opa,
        "address": f"{opa} TEST ST",
        "plaintiff": "CITY OF PHILADELPHIA",
        "sale_type": "TAX",
        "sale_date": sale_date.isoformat(),
        "status": status,
        "opening_bid": 10000.0,
        "source": "civilview",
    }


async def _events(session: AsyncSession) -> list[Any]:
    return list(
        await session.execute(
            text(
                "SELECT case_number, old_status, new_status, old_sale_date, new_sale_date "
                "FROM sheriff_sale_event ORDER BY case_number"
            )
        )
    )


async def test_status_and_date_changes_become_events_and_a_rerun_adds_none(
    db_session: AsyncSession,
) -> None:
    first = [
        _row("CV-1", "000000701", _FUTURE, "Scheduled - Tax"),
        _row("CV-2", "000000702", _FUTURE, "Scheduled - Tax"),
        _row("CV-3", "000000703", _FUTURE, "Scheduled - Tax"),
    ]
    await load_sheriff(db_session, _FakeSource(first))
    await db_session.flush()
    assert await _events(db_session) == [], "the first sighting of a case is not a change"

    changed = [
        _row("CV-1", "000000701", _FUTURE, "Postponed"),
        _row("CV-2", "000000702", _LATER, "Scheduled - Tax"),
        _row("CV-3", "000000703", _FUTURE, "Scheduled - Tax"),
    ]
    await load_sheriff(db_session, _FakeSource(changed))
    await db_session.flush()

    events = await _events(db_session)
    assert len(events) == 2, "one status change and one date move"
    by_case = {e.case_number: e for e in events}
    assert by_case["CV-1"].old_status == "Scheduled - Tax"
    assert by_case["CV-1"].new_status == "Postponed"
    assert by_case["CV-2"].old_sale_date == _FUTURE
    assert by_case["CV-2"].new_sale_date == _LATER
    assert "CV-3" not in by_case, "an unchanged case emits nothing"

    await load_sheriff(db_session, _FakeSource(changed))
    await db_session.flush()
    assert len(await _events(db_session)) == 2, "re-running on unchanged data is idempotent"


async def test_the_search_predicate_returns_only_scheduled_parcels(
    db_session: AsyncSession,
) -> None:
    past = date.today() - timedelta(days=10)
    rows = [
        _row("CV-10", "000000711", _FUTURE, "Scheduled - Tax"),
        _row("CV-11", "000000712", past, "Scheduled - Tax"),
        _row("CV-12", "000000713", _FUTURE, "Sold"),
    ]
    await load_sheriff(db_session, _FakeSource(rows))
    await db_session.flush()

    where, params = build_filters(vacant_only=False, zoning_codes=[], scheduled_for_sale=True)
    found = (
        await db_session.execute(
            text(f"SELECT p.parcel_number FROM parcel p WHERE {where.split(' AND ', 1)[1]}"),
            params,
        )
    ).scalars()
    matched = set(found)

    assert "phl:000000711" in matched, "a future scheduled sale is scheduled"
    assert "phl:000000712" not in matched, "a past sale date is not upcoming"
    assert "phl:000000713" not in matched, "a sold listing is no longer scheduled"


async def test_a_case_that_changes_status_and_date_together_is_one_event(
    db_session: AsyncSession,
) -> None:
    await load_sheriff(
        db_session,
        _FakeSource([_row("CV-20", "000000721", _FUTURE, "Scheduled - Tax")]),
    )
    await db_session.flush()

    await load_sheriff(
        db_session,
        _FakeSource([_row("CV-20", "000000721", _LATER, "Postponed")]),
    )
    await db_session.flush()

    events = await _events(db_session)
    assert len(events) == 1, (
        "one row per changed case, not one per changed field — a postponement moves the "
        "status and the date together and is a single thing that happened"
    )
    event = events[0]
    assert event.old_status == "Scheduled - Tax"
    assert event.new_status == "Postponed"
    assert event.old_sale_date == _FUTURE
    assert event.new_sale_date == _LATER
