from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.opa import OpaRecord, to_parcel_row
from lotscope.ingestion.models import DatasetFreshness
from lotscope.parcels.models import Parcel


def test_to_parcel_row_normalizes_key_and_maps_fields() -> None:
    record = OpaRecord(
        parcel_number="12345",
        location="123 Main St",
        owner_1="Jane Doe",
        market_value=250000.0,
        taxable_land=80000.0,
        exempt_building=120000.0,
        total_area=1200.0,
    )
    row = to_parcel_row(record)
    assert row is not None
    assert row["parcel_number"] == "000012345"
    assert row["address"] == "123 Main St"
    assert row["owner"] == "Jane Doe"
    assert row["market_value"] == 250000.0
    assert row["land_value"] == 80000.0
    assert row["exempt_building"] == 120000.0
    assert row["exempt_land"] is None
    assert row["source"] == "opa_properties_public"


def test_to_parcel_row_skips_unkeyable_record() -> None:
    assert to_parcel_row(OpaRecord(parcel_number=None)) is None
    assert to_parcel_row(OpaRecord(parcel_number="not-a-number")) is None


class _RowsHandler:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        index = min(self.calls, len(self._pages) - 1)
        self.calls += 1
        return httpx.Response(200, json={"rows": self._pages[index]})


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        carto_sql_url="http://carto.test/sql",
        http_backoff_seconds=0.0,
    )


@pytest.mark.integration
async def test_load_opa_upserts_and_records_freshness(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.opa import load_opa

    handler = _RowsHandler(
        [
            [{"parcel_number": "11", "owner_1": "A"}, {"parcel_number": "12", "owner_1": "B"}],
            [{"parcel_number": "13", "owner_1": "C"}],
        ]
    )
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        total = await load_opa(db_session, carto, page_size=2)
    await db_session.flush()

    assert total == 3
    count = await db_session.scalar(select(func.count()).select_from(Parcel))
    assert count == 3
    fresh = await db_session.get(DatasetFreshness, "opa_properties_public")
    assert fresh is not None
    assert fresh.status == "success"
    assert fresh.row_count == 3


@pytest.mark.integration
async def test_load_opa_is_idempotent(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.opa import load_opa

    pages = [[{"parcel_number": "21", "owner_1": "A"}]]
    for _ in range(2):
        handler = _RowsHandler(pages)
        async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
            await load_opa(db_session, carto, page_size=50)
        await db_session.flush()

    count = await db_session.scalar(
        select(func.count()).select_from(Parcel).where(Parcel.parcel_number == "000000021")
    )
    assert count == 1
