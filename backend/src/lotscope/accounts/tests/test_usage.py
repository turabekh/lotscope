from typing import Any, cast

from redis.asyncio import Redis

from lotscope.accounts.usage import (
    get_area_search_parcels,
    get_ask_usage,
    get_export_usage,
    increment_ask_usage,
    register_area_search_parcels,
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

    async def sadd(self, key: str, *members: str) -> int:
        bucket = self.store.setdefault(key, set())
        before = len(bucket)
        bucket.update(members)
        return len(bucket) - before

    async def scard(self, key: str) -> int:
        return len(self.store.get(key, set()))


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


async def test_area_search_quota_counts_distinct_parcels_not_requests() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    for _ in range(5):
        assert await register_area_search_parcels(redis, 1, ["phl:1", "phl:2"], 3) is True
    assert await get_area_search_parcels(redis, 1) == 2

    assert await register_area_search_parcels(redis, 1, ["phl:3", "phl:4"], 3) is True
    assert await register_area_search_parcels(redis, 1, ["phl:5"], 3) is False


async def test_area_search_quota_unlimited_always_allows() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert await register_area_search_parcels(redis, 1, [f"phl:{n}" for n in range(50)], None)
    assert await register_area_search_parcels(redis, 1, ["phl:999"], None) is True


async def test_area_search_quota_is_scoped_per_user() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    assert await register_area_search_parcels(redis, 1, ["phl:1", "phl:2"], 2) is True
    assert await register_area_search_parcels(redis, 1, ["phl:3"], 2) is False
    assert await register_area_search_parcels(redis, 2, ["phl:3"], 2) is True


async def test_area_search_ttl_is_set_only_once() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    await register_area_search_parcels(redis, 1, ["phl:1"], None)
    await register_area_search_parcels(redis, 1, ["phl:2"], None)
    assert len(fake.expires) == 1
