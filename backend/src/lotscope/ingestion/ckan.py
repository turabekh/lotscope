from collections.abc import AsyncIterator, Sequence
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import BaseModel, Field

from lotscope.core.config import Settings
from lotscope.ingestion.carto import build_keyset_query
from lotscope.ingestion.errors import CkanError
from lotscope.ingestion.http import request_with_retry

_DATASTORE_SQL_PATH = "/api/3/action/datastore_search_sql"


class CkanResult(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)


class CkanResponse(BaseModel):
    success: bool = True
    result: CkanResult = Field(default_factory=CkanResult)


class CkanDatastoreClient:
    def __init__(
        self,
        settings: Settings,
        base_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + _DATASTORE_SQL_PATH
        self._max_retries = settings.http_max_retries
        self._backoff = settings.http_backoff_seconds
        self._client = httpx.AsyncClient(transport=transport, timeout=settings.http_timeout_seconds)

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
        response = await request_with_retry(
            lambda: self._client.post(self._url, data={"sql": sql}),
            max_retries=self._max_retries,
            backoff=self._backoff,
            error=CkanError,
        )
        parsed = CkanResponse.model_validate(response.json())
        if not parsed.success:
            raise CkanError("CKAN datastore query reported failure")
        return parsed.result.records

    async def paginate_by_key(
        self,
        *,
        resource_id: str,
        columns: Sequence[str],
        key_column: str,
        page_size: int = 5000,
        where: str | None = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        table = f'"{resource_id}"'
        key_field = key_column.strip('"')
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
            last_key = rows[-1][key_field]
