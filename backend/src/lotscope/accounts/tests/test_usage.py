from typing import Any, cast

from redis.asyncio import Redis

from lotscope.accounts.usage import get_ask_usage, increment_ask_usage


class _Redis:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.expires: list[tuple[str, int]] = []

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def incr(self, key: str) -> int:
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = value
        return value

    async def expire(self, key: str, ttl: int) -> bool:
        self.expires.append((key, ttl))
        return True


async def test_increment_then_get_counts_usage() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert await get_ask_usage(redis, 7) == 0
    assert await increment_ask_usage(redis, 7) == 1
    assert await increment_ask_usage(redis, 7) == 2
    assert await get_ask_usage(redis, 7) == 2


async def test_ttl_is_set_only_on_first_increment() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    await increment_ask_usage(redis, 1)
    await increment_ask_usage(redis, 1)
    assert len(fake.expires) == 1
