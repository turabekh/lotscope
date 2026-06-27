from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any, Self

import httpx
from pydantic import BaseModel, ConfigDict, Field

from lotscope.core.config import Settings
from lotscope.ingestion.errors import ArcGisError
from lotscope.ingestion.http import request_with_retry


class ArcGisFeature(BaseModel):
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class ArcGisResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    features: list[ArcGisFeature] = Field(default_factory=list)
    exceeded_transfer_limit: bool = Field(default=False, alias="exceededTransferLimit")


class ArcGisClient:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
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

    async def query(self, layer_url: str, params: dict[str, str | int]) -> ArcGisResponse:
        response = await request_with_retry(
            lambda: self._client.get(layer_url, params=params),
            max_retries=self._max_retries,
            backoff=self._backoff,
            error=ArcGisError,
        )
        return ArcGisResponse.model_validate(response.json())

    async def paginate(
        self,
        layer_url: str,
        *,
        where: str = "1=1",
        out_fields: str = "*",
        page_size: int = 2000,
        out_sr: int = 4326,
    ) -> AsyncIterator[list[ArcGisFeature]]:
        offset = 0
        while True:
            params: dict[str, str | int] = {
                "where": where,
                "outFields": out_fields,
                "f": "geojson",
                "returnGeometry": "true",
                "outSR": out_sr,
                "resultOffset": offset,
                "resultRecordCount": page_size,
            }
            response = await self.query(layer_url, params)
            if not response.features:
                return
            yield response.features
            if len(response.features) < page_size:
                return
            offset += page_size
