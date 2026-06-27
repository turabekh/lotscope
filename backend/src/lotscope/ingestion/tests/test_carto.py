from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from lotscope.core.config import Settings
from lotscope.ingestion.carto import (
    CartoClient,
    build_keyset_query,
    quote_literal,
)
from lotscope.ingestion.errors import CartoError


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "carto_sql_url": "http://carto.test/sql",
        "http_backoff_seconds": 0.0,
        "http_max_retries": 3,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


class _Handler:
    def __init__(self, steps: list[tuple[int, dict[str, Any]]]) -> None:
        self._steps = steps
        self.queries: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.queries.append(parse_qs(request.content.decode())["q"][0])
        index = min(len(self.queries) - 1, len(self._steps) - 1)
        status, body = self._steps[index]
        return httpx.Response(status, json=body)


def test_quote_literal_escapes_and_formats() -> None:
    assert quote_literal("O'Brien") == "'O''Brien'"
    assert quote_literal(5) == "5"
    assert quote_literal(1.5) == "1.5"


def test_quote_literal_rejects_bool() -> None:
    with pytest.raises(TypeError):
        quote_literal(True)


def test_build_keyset_query_first_page() -> None:
    sql = build_keyset_query(
        table="opa_properties_public",
        columns=["parcel_number", "market_value"],
        key_column="parcel_number",
        page_size=1000,
        where="vacant = true",
    )
    assert sql == (
        "SELECT parcel_number, market_value FROM opa_properties_public "
        "WHERE (vacant = true) ORDER BY parcel_number ASC LIMIT 1000"
    )


def test_build_keyset_query_quotes_last_key() -> None:
    sql = build_keyset_query(
        table="t",
        columns=["parcel_number"],
        key_column="parcel_number",
        page_size=10,
        last_key="00'1",
    )
    assert "parcel_number > '00''1'" in sql


async def test_query_returns_rows() -> None:
    handler = _Handler([(200, {"rows": [{"parcel_number": "001"}]})])
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        rows = await client.query("SELECT 1")
    assert rows == [{"parcel_number": "001"}]


async def test_query_retries_then_succeeds() -> None:
    handler = _Handler([(503, {}), (200, {"rows": [{"parcel_number": "001"}]})])
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        rows = await client.query("SELECT 1")
    assert rows == [{"parcel_number": "001"}]
    assert len(handler.queries) == 2


async def test_query_raises_on_non_retryable_status() -> None:
    handler = _Handler([(400, {})])
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CartoError):
            await client.query("SELECT bad")
    assert len(handler.queries) == 1


async def test_query_raises_after_exhausting_retries() -> None:
    handler = _Handler([(503, {})])
    settings = _settings(http_max_retries=2)
    async with CartoClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(CartoError):
            await client.query("SELECT 1")
    assert len(handler.queries) == 3


async def test_paginate_by_key_walks_pages_with_keyset() -> None:
    handler = _Handler(
        [
            (200, {"rows": [{"parcel_number": "001"}, {"parcel_number": "002"}]}),
            (200, {"rows": [{"parcel_number": "003"}]}),
        ]
    )
    pages: list[list[dict[str, Any]]] = []
    async with CartoClient(_settings(), transport=httpx.MockTransport(handler)) as client:
        async for page in client.paginate_by_key(
            table="opa_properties_public",
            columns=["parcel_number"],
            key_column="parcel_number",
            page_size=2,
        ):
            pages.append(page)
    assert [len(p) for p in pages] == [2, 1]
    assert "parcel_number > '002'" in handler.queries[1]
