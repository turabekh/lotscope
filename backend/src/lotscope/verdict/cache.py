"""The verdict cache.

A verdict is computed when it is read, so nothing stored can be stale. This is what
stops us computing the same one twice: the cached copy is stamped with a fingerprint of
the inputs it was computed from, and a read whose inputs have moved is a miss, not a
stale answer.

The fingerprint covers the parcel's own row and the per-parcel records the verdict reads
(deeds, violations, tax, sheriff listings, overlay membership), the last successful load
of every dataset in the market — which is how the geometry sources change — the two
standards tables that are seeded by hand rather than ingested, and the running code's
git SHA. A deploy therefore invalidates every entry, which is what we want: the same
inputs through different code are a different verdict.

The key is per parcel rather than per fingerprint so that an ingest can drop the entries
it touched in one batched call. The fingerprint travels inside the value, where it is
checked on read.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import get_settings

if TYPE_CHECKING:
    from lotscope.verdict.service import VerdictRead

CACHE_TTL_SECONDS = 86_400

# One round trip for every timestamp the verdict depends on.
_FINGERPRINT_SQL = text(
    "SELECT p.updated_at AS parcel_at, "
    "(SELECT max(updated_at) FROM sale WHERE parcel_number = p.parcel_number) AS sale_at, "
    "(SELECT max(updated_at) FROM li_event WHERE parcel_number = p.parcel_number) AS li_at, "
    "(SELECT updated_at FROM tax_status WHERE parcel_number = p.parcel_number) AS tax_at, "
    "(SELECT max(updated_at) FROM sheriff_sale WHERE parcel_number = p.parcel_number) "
    "  AS sheriff_at, "
    "(SELECT max(updated_at) FROM parcel_overlay WHERE parcel_number = p.parcel_number) "
    "  AS overlay_at, "
    "(SELECT max(last_success_at) FROM dataset_freshness WHERE market_code = p.market_code) "
    "  AS datasets_at, "
    "(SELECT max(updated_at) FROM zoning_standard) AS zoning_standards_at, "
    "(SELECT max(updated_at) FROM overlay_standard) AS overlay_standards_at "
    "FROM parcel p WHERE p.parcel_number = :parcel_number"
)

_CHUNK = 500


def cache_key(parcel_number: str) -> str:
    return f"verdict:{parcel_number}"


async def input_fingerprint(
    session: AsyncSession,
    parcel_number: str,
    *,
    git_sha: str,
    assumptions: Mapping[str, float] | None = None,
) -> str | None:
    """A digest of everything the verdict is computed from, or None if there is no parcel.

    The buyer's underwriting assumptions are part of it: a buyer who has changed none
    hashes the same as everyone else and shares their entry, and one who has changed them
    cannot be served somebody else's numbers.
    """
    row = (await session.execute(_FINGERPRINT_SQL, {"parcel_number": parcel_number})).one_or_none()
    if row is None:
        return None
    stamps = [value.isoformat() if value is not None else "-" for value in row]
    tuned = json.dumps(dict(sorted((assumptions or {}).items())), separators=(",", ":"))
    return hashlib.sha256("|".join([git_sha, tuned, *stamps]).encode("utf-8")).hexdigest()


async def read(redis: Redis, parcel_number: str, fingerprint: str) -> "VerdictRead | None":
    """The cached read, only if it was computed from exactly these inputs."""
    try:
        raw = await redis.get(cache_key(parcel_number))
    except RedisError:
        return None
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if payload.get("inputs") != fingerprint:
        return None
    try:
        from lotscope.verdict.service import VerdictRead

        return VerdictRead.model_validate(payload["read"])
    except (KeyError, ValueError):
        return None


async def write(redis: Redis, parcel_number: str, fingerprint: str, read: "VerdictRead") -> None:
    payload = json.dumps({"inputs": fingerprint, "read": json.loads(read.model_dump_json())})
    try:
        await redis.set(cache_key(parcel_number), payload, ex=CACHE_TTL_SECONDS)
    except RedisError:
        # A cache that cannot be written is a slower read, not a wrong one.
        return


async def invalidate_parcels(redis: Redis, parcel_numbers: Iterable[str]) -> int:
    """Drop the cached verdicts for parcels an ingest touched, in batches.

    A changed input already misses on the fingerprint, so this is about not holding
    entries nobody can use for the rest of the day — and about the case the fingerprint
    cannot see, code that changes what an unchanged row means.
    """
    keys = [cache_key(number) for number in dict.fromkeys(parcel_numbers)]
    dropped = 0
    for start in range(0, len(keys), _CHUNK):
        chunk: Sequence[str] = keys[start : start + _CHUNK]
        try:
            dropped += int(await redis.delete(*chunk))
        except RedisError:
            return dropped
    return dropped


async def invalidate_after_ingest(parcel_numbers: Sequence[str]) -> int:
    """Drop the cached verdicts for parcels a merge step touched.

    This opens its own connection rather than taking one: a loader is handed a session
    and nothing else, and threading a Redis client through five of them to delete a batch
    of keys buys nothing. One connection per merge step, five a night.
    """
    if not parcel_numbers:
        return 0
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    try:
        return await invalidate_parcels(redis, parcel_numbers)
    finally:
        await redis.aclose()
