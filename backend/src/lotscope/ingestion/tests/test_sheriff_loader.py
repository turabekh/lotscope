from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.loaders.sheriff import SheriffSaleRecord, load_sheriff, to_sheriff_row
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.tests.support import open_run


def test_to_sheriff_row_maps_and_normalizes() -> None:
    row = to_sheriff_row(
        SheriffSaleRecord(
            case_number=" BW-1 ",
            opa_number="1234567",
            sale_type="mortgage",
            status="Open",
            sale_date="2026-08-05",
            opening_bid=12000.0,
            plaintiff="BANK",
        )
    )
    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["case_number"] == "BW-1"
    assert row["sale_date"] == date(2026, 8, 5)
    assert row["opening_bid"] == 12000.0
    assert row["source"] == "sheriff_sale"


def test_to_sheriff_row_skips_without_opa_or_case() -> None:
    assert to_sheriff_row(SheriffSaleRecord(case_number="BW-1", opa_number=None)) is None
    assert to_sheriff_row(SheriffSaleRecord(case_number=None, opa_number="1234567")) is None


class _FakeSource:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetch(self) -> list[dict[str, Any]]:
        return self._rows


def _row(case: str, opa: str, price: float) -> dict[str, Any]:
    return {
        "case_number": case,
        "opa_number": opa,
        "sale_type": "mortgage",
        "status": "Open",
        "sale_date": "2026-08-05",
        "opening_bid": price,
        "plaintiff": "BANK",
    }


@pytest.mark.integration
async def test_load_sheriff_inserts_and_records_freshness(db_session: AsyncSession) -> None:
    total = await load_sheriff(
        db_session,
        _FakeSource([_row("BW-1", "1234567", 10000.0)]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    assert total == 1
    parcel = await db_session.scalar(
        text("SELECT count(*) FROM parcel WHERE parcel_number = 'phl:001234567'")
    )
    assert parcel == 1
    bid = await db_session.scalar(
        text("SELECT opening_bid FROM sheriff_sale WHERE case_number = 'BW-1'")
    )
    assert float(bid) == 10000.0
    fresh = await db_session.get(DatasetFreshness, ("phl", "sheriff_sale"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_sheriff_emits_event_for_new_case(db_session: AsyncSession) -> None:
    runs = [
        [_row("BW-1", "1234567", 10000.0)],
        [_row("BW-1", "1234567", 10000.0), _row("BW-2", "1234567", 20000.0)],
    ]
    for rows in runs:
        await load_sheriff(
            db_session,
            _FakeSource(rows),
            run_id=await open_run(db_session, "sheriff_sale"),
        )
        await db_session.flush()

    events = (
        await db_session.execute(
            text(
                "SELECT code, new_value->>'case_number' AS case_number, severity "
                "FROM parcel_event WHERE parcel_number = 'phl:001234567' ORDER BY id"
            )
        )
    ).all()
    assert [(e.code, e.case_number, e.severity) for e in events] == [
        ("sheriff_sale", "BW-2", "high")
    ]


@pytest.mark.integration
async def test_load_sheriff_is_idempotent_on_case(db_session: AsyncSession) -> None:
    for _ in range(2):
        await load_sheriff(
            db_session,
            _FakeSource([_row("BW-9", "1234567", 5000.0)]),
            run_id=await open_run(db_session, "sheriff_sale"),
        )
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM sheriff_sale WHERE case_number = 'BW-9'")
    )
    assert count == 1


@pytest.mark.integration
async def test_load_sheriff_postponement_updates_same_case(db_session: AsyncSession) -> None:
    scheduled = _row("BW-7", "1234567", 5000.0)
    scheduled["sale_date"] = "2026-08-05"
    await load_sheriff(
        db_session,
        _FakeSource([scheduled]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    postponed = _row("BW-7", "1234567", 5000.0)
    postponed["status"] = "Postponed"
    postponed["sale_date"] = "2026-09-16"
    await load_sheriff(
        db_session,
        _FakeSource([postponed]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    rows = (
        await db_session.execute(
            text("SELECT status, sale_date FROM sheriff_sale WHERE case_number = 'BW-7'")
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "Postponed"
    assert rows[0].sale_date == date(2026, 9, 16)


@pytest.mark.integration
async def test_load_sheriff_preserves_detail_fields_when_a_rescrape_bounces(
    db_session: AsyncSession,
) -> None:
    await load_sheriff(
        db_session,
        _FakeSource([_row("BW-5", "1234567", 8000.0)]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    bounced: dict[str, Any] = {
        "case_number": "BW-5",
        "opa_number": "1234567",
        "sale_type": None,
        "status": None,
        "sale_date": None,
        "opening_bid": None,
        "plaintiff": "BANK",
    }
    await load_sheriff(
        db_session,
        _FakeSource([bounced]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    row = (
        await db_session.execute(
            text(
                "SELECT opening_bid, status, sale_date, sale_type "
                "FROM sheriff_sale WHERE case_number = 'BW-5'"
            )
        )
    ).one()
    assert float(row.opening_bid) == 8000.0
    assert row.status == "Open"
    assert row.sale_date == date(2026, 8, 5)
    assert row.sale_type == "mortgage"


@pytest.mark.integration
async def test_load_sheriff_overwrites_bid_when_a_new_value_arrives(
    db_session: AsyncSession,
) -> None:
    await load_sheriff(
        db_session,
        _FakeSource([_row("BW-6", "1234567", 5000.0)]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()
    await load_sheriff(
        db_session,
        _FakeSource([_row("BW-6", "1234567", 7500.0)]),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    bid = await db_session.scalar(
        text("SELECT opening_bid FROM sheriff_sale WHERE case_number = 'BW-6'")
    )
    assert float(bid) == 7500.0


@pytest.mark.integration
async def test_load_sheriff_counts_skipped_rows_in_freshness(db_session: AsyncSession) -> None:
    rows = [
        _row("BW-1", "1234567", 10000.0),
        {**_row("BW-2", "", 20000.0), "opa_number": None},
    ]
    total = await load_sheriff(
        db_session,
        _FakeSource(rows),
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    assert total == 1
    fresh = await db_session.get(DatasetFreshness, ("phl", "sheriff_sale"))
    assert fresh is not None
    assert fresh.detail is not None
    assert "1 of 2 rows skipped" in fresh.detail
    assert "1 without a parcel id" in fresh.detail
    assert "outside this market" not in fresh.detail


@pytest.mark.integration
async def test_skip_detail_separates_out_of_market_rows_from_unidentified_ones(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES ('000000901', 'phl')")
    )
    await db_session.flush()
    rows = [
        {**_row("SS-1", "000000901", 10000.0), "parcel_number": "000000901"},
        {**_row("SS-2", "000000902", 20000.0), "parcel_number": "000000902"},
        {**_row("SS-3", "000000903", 30000.0), "parcel_number": "000000903"},
        {**_row("SS-4", "", 40000.0), "opa_number": None, "parcel_number": None},
    ]
    total = await load_sheriff(
        db_session,
        _FakeSource(rows),
        known_parcels={"000000901"},
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    assert total == 1
    fresh = await db_session.get(DatasetFreshness, ("phl", "sheriff_sale"))
    assert fresh is not None
    assert fresh.detail is not None
    assert "3 of 4 rows skipped" in fresh.detail
    assert "2 outside this market" in fresh.detail
    assert "1 without a parcel id" in fresh.detail


@pytest.mark.integration
async def test_a_fully_reconciled_load_records_no_skip_detail(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, market_code) VALUES ('000000902', 'phl')")
    )
    await db_session.flush()
    rows = [{**_row("SS-9", "000000902", 1000.0), "parcel_number": "000000902"}]

    total = await load_sheriff(
        db_session,
        _FakeSource(rows),
        known_parcels={"000000902"},
        run_id=await open_run(db_session, "sheriff_sale"),
    )
    await db_session.flush()

    assert total == 1
    fresh = await db_session.get(DatasetFreshness, ("phl", "sheriff_sale"))
    assert fresh is not None
    assert fresh.detail is None
