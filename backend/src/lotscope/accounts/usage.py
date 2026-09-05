from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

_TTL_SECONDS = 172_800
_EXPORT_TTL_SECONDS = 3_456_000


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


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


def export_usage_key(user_id: int, month: str) -> str:
    return f"usage:export:{user_id}:{month}"


async def get_export_usage(redis: Redis, user_id: int) -> int:
    value = await redis.get(export_usage_key(user_id, _month()))
    return int(value) if value is not None else 0


async def reserve_export(redis: Redis, user_id: int, monthly_limit: int | None) -> bool:
    if monthly_limit is not None and monthly_limit <= 0:
        return False
    key = export_usage_key(user_id, _month())
    count = int(await redis.incr(key))
    if count == 1:
        await redis.expire(key, _EXPORT_TTL_SECONDS)
    if monthly_limit is not None and count > monthly_limit:
        await redis.decr(key)
        return False
    return True


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


RESEND_LIMIT_PER_HOUR = 3
_RESEND_WINDOW_SECONDS = 3600


def _resend_key(email: str) -> str:
    return f"verify:resend:{email.strip().lower()}"


async def claim_resend_slot(redis: Redis, email: str) -> bool:
    key = _resend_key(email)
    try:
        used = await redis.incr(key)
        if used == 1:
            await redis.expire(key, _RESEND_WINDOW_SECONDS)
    except RedisError:
        return True
    return bool(used <= RESEND_LIMIT_PER_HOUR)
