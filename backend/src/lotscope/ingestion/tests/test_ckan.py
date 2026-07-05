from typing import Any

import httpx
import pytest

from lotscope.core.config import Settings
from lotscope.ingestion.ckan import CkanDatastoreClient
from lotscope.ingestion.errors import CkanError


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"http_backoff_seconds": 0.0, "http_max_retries": 3}
    base.update(overrides)
    return Settings(_env_file=None, **base)


class _Handler:
    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.sql: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        from urllib.parse import parse_qs

        self.sql.append(parse_qs(request.content.decode())["sql"][0])
        index = min(len(self.sql) - 1, len(self._pages) - 1)
        body = {"success": True, "result": {"records": self._pages[index]}}
        return httpx.Response(200, json=body)


async def test_query_returns_records() -> None:
    handler = _Handler([[{"parcel_id": "1"}, {"parcel_id": "2"}]])
    async with CkanDatastoreClient(
        _settings(), "https://data.test", transport=httpx.MockTransport(handler)
    ) as client:
        rows = await client.query('SELECT * FROM "res"')
    assert rows == [{"parcel_id": "1"}, {"parcel_id": "2"}]
    assert client._url == "https://data.test/api/3/action/datastore_search_sql"


async def test_paginate_by_key_chunks_until_short_page() -> None:
    pages = [
        [{"k": "1"}, {"k": "2"}],
        [{"k": "3"}],
    ]
    handler = _Handler(pages)
    async with CkanDatastoreClient(
        _settings(), "https://data.test", transport=httpx.MockTransport(handler)
    ) as client:
        collected = [
            row
            async for page in client.paginate_by_key(
                resource_id="res", columns=["k"], key_column="k", page_size=2
            )
            for row in page
        ]
    assert [row["k"] for row in collected] == ["1", "2", "3"]
    assert 'FROM "res"' in handler.sql[0]
    assert "k > '2'" in handler.sql[1]


async def test_failure_reported() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": False, "result": {"records": []}})

    async with CkanDatastoreClient(
        _settings(), "https://data.test", transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(CkanError):
            await client.query("SELECT 1")
