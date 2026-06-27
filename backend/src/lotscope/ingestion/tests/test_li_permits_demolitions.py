from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.li import (
    DemolitionRecord,
    PermitRecord,
    to_demolition_event_row,
    to_permit_event_row,
)


def test_to_permit_event_row_maps_permit() -> None:
    row = to_permit_event_row(
        PermitRecord(
            permitnumber="P-100",
            opa_account_num="1234567",
            permitdescription="NEW CONSTRUCTION",
            status="ISSUED",
            permitissuedate="2022-06-15",
        )
    )
    assert row is not None
    assert row["event_type"] == "permit"
    assert row["external_id"] == "P-100"
    assert row["description"] == "NEW CONSTRUCTION"


def test_to_demolition_event_row_maps_demolition() -> None:
    row = to_demolition_event_row(
        DemolitionRecord(caseorpermitnumber="D-9", opa_account_num="1234567", status="COMPLETED")
    )
    assert row is not None
    assert row["event_type"] == "demolition"
    assert row["external_id"] == "D-9"


def test_event_rows_skip_without_key_or_id() -> None:
    assert to_permit_event_row(PermitRecord(opa_account_num=None, permitnumber="1")) is None
    assert to_demolition_event_row(DemolitionRecord(opa_account_num="1234567")) is None


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
async def test_load_li_permits_and_demolitions_coexist(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.li import load_li_demolitions, load_li_permits

    permit_handler = _RowsHandler(
        [
            [
                {
                    "cartodb_id": 1,
                    "permitnumber": "SHARED-1",
                    "opa_account_num": "1234567",
                    "permitdescription": "ALTERATION",
                    "status": "ISSUED",
                    "permitissuedate": "2022-01-01",
                }
            ]
        ]
    )
    demo_handler = _RowsHandler(
        [
            [
                {
                    "cartodb_id": 1,
                    "caseorpermitnumber": "SHARED-1",
                    "opa_account_num": "1234567",
                    "status": "COMPLETED",
                    "start_date": "2022-02-01",
                }
            ]
        ]
    )
    async with CartoClient(_settings(), transport=httpx.MockTransport(permit_handler)) as carto:
        await load_li_permits(db_session, carto, page_size=500)
    async with CartoClient(_settings(), transport=httpx.MockTransport(demo_handler)) as carto:
        await load_li_demolitions(db_session, carto, page_size=500)
    await db_session.flush()

    types = await db_session.scalars(
        text("SELECT event_type FROM li_event WHERE external_id = 'SHARED-1' ORDER BY event_type")
    )
    assert list(types) == ["demolition", "permit"]
