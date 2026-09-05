import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from lotscope.core.config import Settings
from lotscope.core.logging import get_logger

_logger = get_logger(__name__)

CACHE_PREFIX = "live"


@dataclass(frozen=True)
class CachedFetch:
    """A live read, and whether it came off the wire or out of the cache.

    `from_cache` is the whole reason this type exists: a cached read is a repeat of a
    question we already answered, so it must not file a second correction for the same
    disagreement.
    """

    payload: dict[str, Any]
    fetched_at: datetime
    from_cache: bool


def cache_key(tool: str, argument: str) -> str:
    return f"{CACHE_PREFIX}:{tool}:{argument.strip().casefold()}"


async def cached_fetch(
    redis: Redis | None,
    settings: Settings,
    *,
    tool: str,
    argument: str,
    fetch: Callable[[], Awaitable[dict[str, Any]]],
) -> CachedFetch:
    key = cache_key(tool, argument)

    if redis is not None:
        try:
            raw = await redis.get(key)
        except RedisError:
            raw = None
        if raw is not None:
            try:
                stored = json.loads(raw)
                return CachedFetch(
                    payload=stored["payload"],
                    fetched_at=datetime.fromisoformat(stored["fetched_at"]),
                    from_cache=True,
                )
            except (ValueError, KeyError, TypeError):
                # A corrupt entry is not worth failing over; read it live instead.
                pass

    payload = await fetch()
    fetched_at = datetime.now(UTC)

    if redis is not None:
        try:
            await redis.set(
                key,
                json.dumps({"payload": payload, "fetched_at": fetched_at.isoformat()}, default=str),
                ex=settings.live_verify_cache_seconds,
            )
        except RedisError as cause:
            # Caching is an optimisation: losing it costs a request, not an answer. It is
            # still logged — a cache that silently never writes is a cache that lies about
            # how often we are hitting the source.
            _logger.warning("live_cache_write_failed", key=key, error=str(cause))

    return CachedFetch(payload=payload, fetched_at=fetched_at, from_cache=False)
