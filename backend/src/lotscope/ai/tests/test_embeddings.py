from typing import Any

import httpx
import pytest

from lotscope.ai.embeddings import VoyageEmbedder
from lotscope.ai.errors import EmbeddingError
from lotscope.core.config import Settings


def _settings() -> Settings:
    return Settings(_env_file=None, voyage_url="http://voyage.test/embeddings", voyage_api_key="k")


def _handler(status: int, body: dict[str, Any]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handle)


async def test_embed_parses_vectors() -> None:
    body = {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}
    async with VoyageEmbedder(_settings(), transport=_handler(200, body)) as embedder:
        vectors = await embedder.embed(["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


async def test_embed_raises_on_http_error() -> None:
    async with VoyageEmbedder(_settings(), transport=_handler(500, {})) as embedder:
        with pytest.raises(EmbeddingError):
            await embedder.embed(["a"])
