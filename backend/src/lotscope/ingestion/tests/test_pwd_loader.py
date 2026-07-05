from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.loaders.pwd import PwdRecord, to_parcel_geometry_row
from lotscope.ingestion.models import DatasetFreshness

_POLYGON = (
    '{"type":"Polygon","coordinates":'
    "[[[-75.16,39.95],[-75.16,39.951],[-75.159,39.951],[-75.159,39.95],[-75.16,39.95]]]}"
)


def test_to_parcel_geometry_row_maps_key_and_geometry() -> None:
    row = to_parcel_geometry_row(
        PwdRecord(brt_id="1234567", parcel_id="pwd-9", geom_geojson=_POLYGON)
    )
    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["pwd_parcel_id"] == "PWD-9"
    assert "geom_4326" in row
    assert "geom_local" in row
    assert row["source"] == "pwd_parcels"


def test_to_parcel_geometry_row_skips_without_key_or_geometry() -> None:
    assert to_parcel_geometry_row(PwdRecord(brt_id=None, geom_geojson=_POLYGON)) is None
    assert to_parcel_geometry_row(PwdRecord(brt_id="1234567", geom_geojson=None)) is None


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
async def test_load_pwd_writes_dual_srid_geometry(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.pwd import load_pwd

    handler = _RowsHandler(
        [[{"cartodb_id": 1, "brt_id": "1234567", "parcel_id": "p9", "geom_geojson": _POLYGON}]]
    )
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        total = await load_pwd(db_session, carto, page_size=500)
    await db_session.flush()

    assert total == 1
    row = (
        await db_session.execute(
            text(
                "SELECT ST_SRID(geom_local), ST_SRID(geom_4326), pwd_parcel_id, source "
                "FROM parcel WHERE parcel_number = :pn"
            ),
            {"pn": "phl:001234567"},
        )
    ).one()
    assert row[0] == 2272
    assert row[1] == 4326
    assert row[2] == "P9"
    assert row[3] == "pwd_parcels"

    fresh = await db_session.get(DatasetFreshness, ("phl", "pwd_parcels"))
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_pwd_composes_with_existing_parcel(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.pwd import load_pwd

    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:001234567', 'Existing Owner')")
    )
    await db_session.flush()

    handler = _RowsHandler(
        [[{"cartodb_id": 1, "brt_id": "1234567", "parcel_id": "p9", "geom_geojson": _POLYGON}]]
    )
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as carto:
        await load_pwd(db_session, carto, page_size=500)
    await db_session.flush()

    row = (
        await db_session.execute(
            text("SELECT owner, ST_SRID(geom_4326) FROM parcel WHERE parcel_number = :pn"),
            {"pn": "phl:001234567"},
        )
    ).one()
    assert row[0] == "Existing Owner"
    assert row[1] == 4326
