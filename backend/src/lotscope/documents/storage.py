from pathlib import Path
from typing import Protocol


class BlobStore(Protocol):
    async def put(self, key: str, data: bytes) -> str: ...

    async def get(self, key: str) -> bytes: ...


class LocalBlobStore:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        return self._root / key

    async def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()
