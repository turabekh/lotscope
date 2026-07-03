from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.tax import TaxRecord, to_tax_row
from lotscope.ingestion.models import DatasetFreshness


def test_to_tax_row_flags_delinquency() -> None:
    row = to_tax_row(
        TaxRecord(opa_number="1234567", total_due=5000.0, principal_due=4000.0, num_years_owed=3)
    )
    assert row is not None
    assert row["parcel_number"] == "001234567"
    assert row["is_delinquent"] is True
    assert row["years_owed"] == 3


def test_to_tax_row_not_delinquent_when_nothing_due() -> None:
    row = to_tax_row(TaxRecord(opa_number="1234567", total_due=0.0))
    assert row is not None
    assert row["is_delinquent"] is False


def test_to_tax_row_skips_unkeyable() -> None:
    assert to_tax_row(TaxRecord(opa_number=None)) is None


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


@pytest.mark.integration
async def test_load_tax_upserts_status_and_stubs_parcel(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.tax import load_tax

    handler = _RowsHandler(
        [[{"cartodb_id": 1, "opa_number": "1234567", "total_due": 9000.0, "num_years_owed": 2}]]
    )
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        total = await load_tax(db_session, carto, page_size=500)
    await db_session.flush()

    assert total == 1
    status = (
        await db_session.execute(
            text(
                "SELECT total_due, years_owed, is_delinquent FROM tax_status "
                "WHERE parcel_number = '001234567'"
            )
        )
    ).one()
    assert status[0] == 9000
    assert status[1] == 2
    assert status[2] is True

    fresh = await db_session.get(DatasetFreshness, "real_estate_tax_delinquencies")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_tax_is_idempotent(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.tax import load_tax

    pages = [[{"cartodb_id": 1, "opa_number": "1234567", "total_due": 100.0}]]
    for _ in range(2):
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_tax(db_session, carto, page_size=500)
        await db_session.flush()

    count = await db_session.scalar(
        text("SELECT count(*) FROM tax_status WHERE parcel_number = '001234567'")
    )
    assert count == 1


@pytest.mark.integration
async def test_load_tax_emits_event_on_second_run_change(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.tax import load_tax

    runs = [
        [[{"cartodb_id": 1, "opa_number": "1234567", "total_due": 100.0}]],
        [[{"cartodb_id": 1, "opa_number": "1234567", "total_due": 500.0}]],
    ]
    for pages in runs:
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_tax(db_session, carto, page_size=500)
        await db_session.flush()

    codes = (
        await db_session.execute(
            text("SELECT code FROM parcel_event WHERE parcel_number = '001234567' ORDER BY code")
        )
    ).scalars().all()
    assert codes == ["tax_up"]
