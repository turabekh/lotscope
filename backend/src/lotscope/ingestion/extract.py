import csv
import hashlib
import io
from types import TracebackType
from typing import Any, Self

import httpx

from lotscope.core.config import Settings
from lotscope.ingestion.errors import ExtractError
from lotscope.ingestion.http import request_with_retry


class ExtractDownload:
    def __init__(self, *, sha256: str, content: bytes) -> None:
        self.sha256 = sha256
        self.content = content


class ExtractClient:
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

    async def download(self, url: str, *, expected_sha256: str | None = None) -> ExtractDownload:
        response = await request_with_retry(
            lambda: self._client.get(url),
            max_retries=self._max_retries,
            backoff=self._backoff,
            error=ExtractError,
        )
        content = response.content
        digest = hashlib.sha256(content).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ExtractError(
                f"checksum mismatch for {url}: expected {expected_sha256}, got {digest}"
            )
        return ExtractDownload(sha256=digest, content=content)

    async def fetch_csv_records(
        self, url: str, *, expected_sha256: str | None = None
    ) -> tuple[str, list[dict[str, Any]]]:
        download = await self.download(url, expected_sha256=expected_sha256)
        text = download.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        return download.sha256, list(reader)
