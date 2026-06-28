from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import cast

from redis.asyncio import Redis

_TTL_SECONDS = 172_800


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def ask_usage_key(user_id: int, day: str) -> str:
    return f"usage:ask:{user_id}:{day}"


async def get_ask_usage(redis: Redis, user_id: int) -> int:
    value = await redis.get(ask_usage_key(user_id, _today()))
    return int(value) if value is not None else 0


async def increment_ask_usage(redis: Redis, user_id: int) -> int:
    key = ask_usage_key(user_id, _today())
    count = int(await redis.incr(key))
    if count == 1:
        await redis.expire(key, _TTL_SECONDS)
    return count


def parcel_view_key(user_id: int, day: str) -> str:
    return f"views:parcel:{user_id}:{day}"


async def get_parcel_views(redis: Redis, user_id: int) -> int:
    return int(await cast("Awaitable[int]", redis.scard(parcel_view_key(user_id, _today()))))


async def register_parcel_view(
    redis: Redis, user_id: int, parcel_number: str, limit: int | None
) -> bool:
    key = parcel_view_key(user_id, _today())
    if await cast("Awaitable[bool]", redis.sismember(key, parcel_number)):
        return True
    if limit is not None and int(await cast("Awaitable[int]", redis.scard(key))) >= limit:
        return False
    added = int(await cast("Awaitable[int]", redis.sadd(key, parcel_number)))
    if added and int(await cast("Awaitable[int]", redis.scard(key))) == 1:
        await redis.expire(key, _TTL_SECONDS)
    return True
