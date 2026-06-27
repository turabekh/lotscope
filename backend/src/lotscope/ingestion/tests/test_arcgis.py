from typing import Any

import httpx
import pytest

from lotscope.core.config import Settings
from lotscope.ingestion.arcgis import ArcGisClient
from lotscope.ingestion.errors import ArcGisError

LAYER_URL = "http://arcgis.test/FeatureServer/0/query"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"http_backoff_seconds": 0.0, "http_max_retries": 3}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _feature(object_id: int) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [0, 0]},
        "properties": {"OBJECTID": object_id},
    }


class _Handler:
    def __init__(self, steps: list[tuple[int, dict[str, Any]]]) -> None:
        self._steps = steps
        self.offsets: list[str | None] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.offsets.append(request.url.params.get("resultOffset"))
        index = min(len(self.offsets) - 1, len(self._steps) - 1)
        status, body = self._steps[index]
        return httpx.Response(status, json=body)


async def test_query_parses_features_and_transfer_limit() -> None:
    body = {
        "type": "FeatureCollection",
        "features": [_feature(1)],
        "exceededTransferLimit": True,
    }
    handler = _Handler([(200, body)])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        response = await client.query(LAYER_URL, {"where": "1=1"})
    assert len(response.features) == 1
    assert response.features[0].properties["OBJECTID"] == 1
    assert response.exceeded_transfer_limit is True


async def test_query_raises_on_non_retryable_status() -> None:
    handler = _Handler([(400, {})])
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ArcGisError):
            await client.query(LAYER_URL, {"where": "1=1"})


async def test_paginate_advances_offset_until_partial_page() -> None:
    handler = _Handler(
        [
            (200, {"features": [_feature(1), _feature(2)]}),
            (200, {"features": [_feature(3)]}),
        ]
    )
    pages = []
    async with ArcGisClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        async for page in client.paginate(LAYER_URL, page_size=2):
            pages.append(page)
    assert [len(p) for p in pages] == [2, 1]
    assert handler.offsets == ["0", "2"]
