from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient, ArcGisFeature
from lotscope.ingestion.loaders.vacancy import to_vacancy_row
from lotscope.ingestion.models import DatasetFreshness

LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def test_to_vacancy_row_normalizes_key() -> None:
    row = to_vacancy_row(ArcGisFeature(properties={"OPA_ID": "1234567"}))
    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["is_vacant"] is True


def test_to_vacancy_row_skips_unkeyable() -> None:
    assert to_vacancy_row(ArcGisFeature(properties={})) is None


class _FeatureHandler:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        index = min(self.calls, len(self._pages) - 1)
        self.calls += 1
        return httpx.Response(
            200, json={"type": "FeatureCollection", "features": self._pages[index]}
        )


def _settings() -> Settings:
    return Settings(_env_file=None, http_backoff_seconds=0.0)


def _feature(opa: str) -> dict[str, Any]:
    return {"type": "Feature", "geometry": None, "properties": {"OPA_ID": opa}}


@pytest.mark.integration
async def test_load_vacancy_marks_parcel_vacant(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.vacancy import load_vacancy

    handler = _FeatureHandler([[_feature("1234567")]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        total = await load_vacancy(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    assert total == 1
    is_vacant = await db_session.scalar(
        text("SELECT is_vacant FROM parcel WHERE parcel_number = 'phl:001234567'")
    )
    assert is_vacant is True

    fresh = await db_session.get(DatasetFreshness, "vacant_indicators")
    assert fresh is not None
    assert fresh.status == "success"


@pytest.mark.integration
async def test_load_vacancy_preserves_existing_attributes(db_session: AsyncSession) -> None:
    from lotscope.ingestion.loaders.vacancy import load_vacancy

    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, owner) VALUES ('phl:001234567', 'Owner X')")
    )
    await db_session.flush()

    handler = _FeatureHandler([[_feature("1234567")]])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as arcgis:
        await load_vacancy(db_session, arcgis, layer_url=LAYER_URL, page_size=500)
    await db_session.flush()

    row = (
        await db_session.execute(
            text("SELECT owner, is_vacant FROM parcel WHERE parcel_number = 'phl:001234567'")
        )
    ).one()
    assert row[0] == "Owner X"
    assert row[1] is True
