from typing import Any, cast

from redis.asyncio import Redis

from lotscope.accounts.usage import (
    RESEND_LIMIT_PER_HOUR,
    claim_resend_slot,
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


async def test_verification_resends_are_capped_per_hour_per_address() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    for _ in range(RESEND_LIMIT_PER_HOUR):
        assert await claim_resend_slot(redis, "someone@example.test") is True
    assert await claim_resend_slot(redis, "someone@example.test") is False
    assert await claim_resend_slot(redis, "another@example.test") is True


async def test_the_resend_cap_ignores_address_case_and_padding() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    for _ in range(RESEND_LIMIT_PER_HOUR):
        assert await claim_resend_slot(redis, "Someone@Example.test") is True
    assert await claim_resend_slot(redis, "  someone@example.TEST ") is False


async def test_the_resend_window_is_set_once_per_address() -> None:
    fake = _Redis()
    redis = cast(Redis, fake)
    await claim_resend_slot(redis, "window@example.test")
    await claim_resend_slot(redis, "window@example.test")
    assert len(fake.expires) == 1
