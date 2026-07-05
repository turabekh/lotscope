import hashlib
from typing import Any

import httpx
import pytest

from lotscope.core.config import Settings
from lotscope.ingestion.errors import ExtractError
from lotscope.ingestion.extract import ExtractClient

_CSV = b"parcel,owner\n001,ALICE\n002,BOB\n"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"http_backoff_seconds": 0.0, "http_max_retries": 3}
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _transport(content: bytes) -> httpx.MockTransport:
    return httpx.MockTransport(lambda _request: httpx.Response(200, content=content))


async def test_download_computes_checksum() -> None:
    async with ExtractClient(_settings(), transport=_transport(_CSV)) as client:
        result = await client.download("https://x.test/f.csv")
    assert result.content == _CSV
    assert result.sha256 == hashlib.sha256(_CSV).hexdigest()


async def test_download_verifies_expected_checksum() -> None:
    async with ExtractClient(_settings(), transport=_transport(_CSV)) as client:
        with pytest.raises(ExtractError, match="checksum mismatch"):
            await client.download("https://x.test/f.csv", expected_sha256="deadbeef")


async def test_fetch_csv_records_parses_rows() -> None:
    async with ExtractClient(_settings(), transport=_transport(_CSV)) as client:
        digest, rows = await client.fetch_csv_records("https://x.test/f.csv")
    assert digest == hashlib.sha256(_CSV).hexdigest()
    assert rows == [
        {"parcel": "001", "owner": "ALICE"},
        {"parcel": "002", "owner": "BOB"},
    ]
