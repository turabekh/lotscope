from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.rtt import RttRecord, to_sale_row
from lotscope.ingestion.models import DatasetFreshness
from lotscope.ingestion.parsing import parse_iso_date
from lotscope.valuation.models import Sale


def test_parse_iso_date_handles_dates_and_timestamps() -> None:
    assert parse_iso_date("2021-05-12") == date(2021, 5, 12)
    assert parse_iso_date("2021-05-12T00:00:00Z") == date(2021, 5, 12)
    assert parse_iso_date(None) is None
    assert parse_iso_date("garbage") is None


def test_to_sale_row_maps_and_normalizes() -> None:
    row = to_sale_row(
        RttRecord(
            opa_account_num="1234567",
            document_id=55512345,
            document_type="DEED",
            recording_date="2022-03-01T00:00:00",
            grantors="Seller",
            grantees="Buyer",
            total_consideration=300000.0,
        )
    )
    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["document_id"] == "55512345"
    assert row["sale_date"] == date(2022, 3, 1)
    assert row["sale_price"] == 300000.0
    assert row["source"] == "rtt_summary"


def test_to_sale_row_skips_without_key_or_document() -> None:
    assert to_sale_row(RttRecord(opa_account_num=None, document_id="1")) is None
    assert to_sale_row(RttRecord(opa_account_num="1234567", document_id=None)) is None


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


def _rtt_row(cartodb_id: int, document_id: str, price: float) -> dict[str, Any]:
    return {
        "cartodb_id": cartodb_id,
        "document_id": document_id,
        "document_type": "DEED",
        "recording_date": "2022-01-01",
        "opa_account_num": "1234567",
        "grantors": "Seller",
        "grantees": "Buyer",
        "total_consideration": price,
    }


@pytest.mark.integration
async def test_load_rtt_stubs_parcel_and_inserts_sale(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.rtt import load_rtt

    handler = _RowsHandler([[_rtt_row(1, "DOC-1", 250000.0)]])
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        total = await load_rtt(db_session, carto, page_size=500)
    await db_session.flush()

    assert total == 1
    parcel_exists = await db_session.scalar(
        text("SELECT count(*) FROM parcel WHERE parcel_number = 'phl:001234567'")
    )
    assert parcel_exists == 1
    sale = (
        await db_session.execute(
            select(Sale.sale_price, Sale.document_type).where(Sale.document_id == "DOC-1")
        )
    ).one()
    assert sale.sale_price == 250000.0
    assert sale.document_type == "DEED"

    fresh = await db_session.get(DatasetFreshness, "rtt_summary")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_rtt_is_idempotent_on_document(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.rtt import load_rtt

    pages = [[_rtt_row(1, "DOC-9", 100000.0)]]
    for _ in range(2):
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_rtt(db_session, carto, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(
        select(func.count()).select_from(Sale).where(Sale.document_id == "DOC-9")
    )
    assert count == 1


@pytest.mark.integration
async def test_load_rtt_emits_new_deed_for_new_document(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.rtt import load_rtt

    runs = [
        [[_rtt_row(1, "DOC-1", 100000.0)]],
        [[_rtt_row(1, "DOC-1", 100000.0), _rtt_row(2, "DOC-2", 200000.0)]],
    ]
    for pages in runs:
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_rtt(db_session, carto, page_size=500)
        await db_session.flush()

    events = (
        await db_session.execute(
            text(
                "SELECT code, new_value->>'document_id' AS doc FROM parcel_event "
                "WHERE parcel_number = 'phl:001234567' ORDER BY id"
            )
        )
    ).all()
    assert [(e.code, e.doc) for e in events] == [("new_deed", "DOC-2")]
