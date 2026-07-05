from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.loaders.sheriff import SheriffSaleRecord, load_sheriff, to_sheriff_row
from lotscope.ingestion.models import DatasetFreshness


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
    total = await load_sheriff(db_session, _FakeSource([_row("BW-1", "1234567", 10000.0)]))
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
    fresh = await db_session.get(DatasetFreshness, "sheriff_sale")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_sheriff_emits_event_for_new_case(db_session: AsyncSession) -> None:
    runs = [
        [_row("BW-1", "1234567", 10000.0)],
        [_row("BW-1", "1234567", 10000.0), _row("BW-2", "1234567", 20000.0)],
    ]
    for rows in runs:
        await load_sheriff(db_session, _FakeSource(rows))
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
        await load_sheriff(db_session, _FakeSource([_row("BW-9", "1234567", 5000.0)]))
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM sheriff_sale WHERE case_number = 'BW-9'")
    )
    assert count == 1
