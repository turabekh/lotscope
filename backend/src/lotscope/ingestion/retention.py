from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import CursorResult, text
from sqlalchemy.ext.asyncio import AsyncSession

_DELETE_RAW_SQL = text(
    "DELETE FROM raw.raw_record WHERE fetched_at < now() - make_interval(days => :days)"
)

_DELETE_EVENTS_SQL = text(
    "DELETE FROM parcel_event WHERE detected_at < now() - make_interval(months => :months)"
)


@dataclass(frozen=True)
class RetentionResult:
    raw_deleted: int
    events_deleted: int


async def sweep_retention(
    session: AsyncSession,
    *,
    raw_retention_days: int,
    event_retention_months: int,
) -> RetentionResult:
    raw = cast(
        "CursorResult[Any]",
        await session.execute(_DELETE_RAW_SQL, {"days": raw_retention_days}),
    )
    events = cast(
        "CursorResult[Any]",
        await session.execute(_DELETE_EVENTS_SQL, {"months": event_retention_months}),
    )
    return RetentionResult(raw_deleted=raw.rowcount, events_deleted=events.rowcount)
