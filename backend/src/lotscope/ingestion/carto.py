import asyncio
from collections.abc import AsyncIterator, Sequence
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import BaseModel, Field

from lotscope.core.config import Settings
from lotscope.ingestion.errors import CartoError

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def quote_literal(value: str | int | float) -> str:
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid SQL keyset literal")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def build_keyset_query(
    *,
    table: str,
    columns: Sequence[str],
    key_column: str,
    page_size: int,
    last_key: str | int | float | None = None,
    where: str | None = None,
) -> str:
    selected = ", ".join(columns)
    clauses: list[str] = []
    if where:
        clauses.append(f"({where})")
    if last_key is not None:
        clauses.append(f"{key_column} > {quote_literal(last_key)}")
    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return (
        f"SELECT {selected} FROM {table}{where_sql} "
        f"ORDER BY {key_column} ASC LIMIT {int(page_size)}"
    )


class CartoResponse(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    total_rows: int | None = None


class CartoClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._url = settings.carto_sql_url
        self._max_retries = settings.http_max_retries
        self._backoff = settings.http_backoff_seconds
        self._client = httpx.AsyncClient(
            transport=transport, timeout=settings.http_timeout_seconds
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def query(self, sql: str) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.post(self._url, data={"q": sql})
                response.raise_for_status()
            except httpx.HTTPStatusError as status_error:
                last_error = status_error
                if status_error.response.status_code not in _RETRYABLE_STATUS:
                    raise CartoError(
                        f"Carto returned {status_error.response.status_code}"
                    ) from status_error
            except httpx.HTTPError as transport_error:
                last_error = transport_error
            else:
                return CartoResponse.model_validate(response.json()).rows
            if attempt < self._max_retries:
                await asyncio.sleep(self._backoff * (2**attempt))
        raise CartoError("Carto request failed after retries") from last_error

    async def paginate_by_key(
        self,
        *,
        table: str,
        columns: Sequence[str],
        key_column: str,
        page_size: int = 5000,
        where: str | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        last_key: str | int | float | None = None
        while True:
            rows = await self.query(
                build_keyset_query(
                    table=table,
                    columns=columns,
                    key_column=key_column,
                    page_size=page_size,
                    last_key=last_key,
                    where=where,
                )
            )
            if not rows:
                return
            yield rows
            if len(rows) < page_size:
                return
            last_key = rows[-1][key_column]
