from typing import Any, cast

from redis.asyncio import Redis

from lotscope.accounts.usage import (
    get_ask_usage,
    get_export_usage,
    increment_ask_usage,
    reserve_export,
)


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

    async def decr(self, key: str) -> int:
        value = int(self.store.get(key, 0)) - 1
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


async def test_reserve_export_rejects_zero_limit_without_counting() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert await reserve_export(redis, 5, 0) is False
    assert await get_export_usage(redis, 5) == 0


async def test_reserve_export_counts_up_to_limit_then_rejects() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert [await reserve_export(redis, 5, 3) for _ in range(4)] == [True, True, True, False]
    assert await get_export_usage(redis, 5) == 3


async def test_reserve_export_unlimited_always_allows() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert all([await reserve_export(redis, 5, None) for _ in range(5)])
    assert await get_export_usage(redis, 5) == 5
