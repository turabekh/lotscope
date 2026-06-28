from datetime import UTC, datetime

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
