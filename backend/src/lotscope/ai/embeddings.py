from types import TracebackType
from typing import Protocol, Self

import httpx
from pydantic import BaseModel

from lotscope.ai.errors import EmbeddingError
from lotscope.core.config import Settings
from lotscope.ingestion.http import request_with_retry


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class _VoyageItem(BaseModel):
    embedding: list[float]


class _VoyageResponse(BaseModel):
    data: list[_VoyageItem]


class VoyageEmbedder:
    def __init__(
        self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._url = settings.voyage_url
        self._api_key = settings.voyage_api_key
        self._model = settings.embedding_model
        self._max_retries = settings.embedding_max_retries
        self._backoff = settings.http_backoff_seconds
        self._client = httpx.AsyncClient(
            transport=transport, timeout=settings.embedding_timeout_seconds
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

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await request_with_retry(
            lambda: self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": texts},
            ),
            max_retries=self._max_retries,
            backoff=self._backoff,
            error=EmbeddingError,
        )
        parsed = _VoyageResponse.model_validate(response.json())
        return [item.embedding for item in parsed.data]
