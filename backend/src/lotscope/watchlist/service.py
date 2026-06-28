from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.watchlist.changes import compute_changes
from lotscope.watchlist.models import SavedParcel
from lotscope.watchlist.schemas import (
    SavedParcelCreate,
    SavedParcelUpdate,
    WatchlistChange,
    WatchlistItem,
)

_STATE_SELECT = (
    "p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score, "
    "ts.is_delinquent, ts.total_due, ts.in_sheriff_sale, "
    "(SELECT count(*) FILTER (WHERE event_type = 'violation') FROM li_event le "
    " WHERE le.parcel_number = p.parcel_number) AS violations, "
    "(SELECT bool_or(coalesce(is_unsafe, false) OR coalesce(is_imminently_dangerous, false)) "
    " FROM li_event le WHERE le.parcel_number = p.parcel_number) AS dangerous, "
    "pd.score AS distress_score"
)
_STATE_JOINS = (
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "LEFT JOIN tax_status ts ON ts.parcel_number = p.parcel_number "
    "LEFT JOIN parcel_distress pd ON pd.parcel_number = p.parcel_number"
)
_PARCEL_STATE_SQL = text(
    f"SELECT {_STATE_SELECT} FROM parcel p {_STATE_JOINS} WHERE p.parcel_number = :parcel_number"
)
_LIST_SQL = text(
    f"SELECT sp.parcel_number, sp.tags, sp.note, sp.created_at, sp.snapshot, "
    f"p.address, p.owner, p.base_zoning_code, {_STATE_SELECT} "
    f"FROM saved_parcel sp JOIN parcel p ON p.parcel_number = sp.parcel_number {_STATE_JOINS} "
    "WHERE sp.user_id = :user_id ORDER BY sp.created_at DESC"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _state_from_row(row: Row[Any]) -> dict[str, Any]:
    return {
        "is_vacant": bool(row.is_vacant) if row.is_vacant is not None else None,
        "market_value": _as_float(row.market_value),
        "opportunity_score": row.opportunity_score,
        "is_delinquent": bool(row.is_delinquent) if row.is_delinquent is not None else None,
        "total_due": _as_float(row.total_due),
        "in_sheriff_sale": bool(row.in_sheriff_sale) if row.in_sheriff_sale is not None else None,
        "violations": int(row.violations or 0),
        "dangerous": bool(row.dangerous),
        "distress_score": row.distress_score,
    }


async def _parcel_state(session: AsyncSession, parcel_number: str) -> dict[str, Any] | None:
    row = (await session.execute(_PARCEL_STATE_SQL, {"parcel_number": parcel_number})).one_or_none()
    return _state_from_row(row) if row is not None else None


async def count_saved(session: AsyncSession, user_id: int) -> int:
    total = await session.scalar(
        select(func.count()).select_from(SavedParcel).where(SavedParcel.user_id == user_id)
    )
    return int(total or 0)


async def is_saved(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    return await session.get(SavedParcel, (user_id, parcel_number)) is not None


async def add_saved(
    session: AsyncSession,
    user_id: int,
    data: SavedParcelCreate,
    *,
    limit: int | None,
) -> SavedParcel:
    state = await _parcel_state(session, data.parcel_number)
    if state is None:
        raise NotFoundError(f"Parcel {data.parcel_number} was not found.")
    item = await session.get(SavedParcel, (user_id, data.parcel_number))
    if item is None:
        if limit is not None and await count_saved(session, user_id) >= limit:
            raise QuotaExceededError(
                f"Your plan can save up to {limit} parcels. Remove one or upgrade to save more."
            )
        item = SavedParcel(
            user_id=user_id,
            parcel_number=data.parcel_number,
            tags=data.tags,
            note=data.note,
            snapshot=state,
            snapshot_at=datetime.now(UTC),
        )
        session.add(item)
    else:
        item.tags = data.tags
        item.note = data.note
    await session.flush()
    return item


async def update_saved(
    session: AsyncSession, user_id: int, parcel_number: str, data: SavedParcelUpdate
) -> SavedParcel:
    item = await session.get(SavedParcel, (user_id, parcel_number))
    if item is None:
        raise NotFoundError(f"Parcel {parcel_number} is not on your watchlist.")
    if data.tags is not None:
        item.tags = data.tags
    if data.note is not None:
        item.note = data.note
    await session.flush()
    return item


async def acknowledge(session: AsyncSession, user_id: int, parcel_number: str) -> SavedParcel:
    item = await session.get(SavedParcel, (user_id, parcel_number))
    if item is None:
        raise NotFoundError(f"Parcel {parcel_number} is not on your watchlist.")
    item.snapshot = await _parcel_state(session, parcel_number)
    item.snapshot_at = datetime.now(UTC)
    await session.flush()
    return item


async def remove_saved(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    item = await session.get(SavedParcel, (user_id, parcel_number))
    if item is None:
        return False
    await session.delete(item)
    await session.flush()
    return True


async def list_saved(session: AsyncSession, user_id: int) -> list[WatchlistItem]:
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    items: list[WatchlistItem] = []
    for row in rows:
        changes = compute_changes(row.snapshot, _state_from_row(row))
        items.append(
            WatchlistItem(
                parcel_number=row.parcel_number,
                address=row.address,
                owner=row.owner,
                base_zoning_code=row.base_zoning_code,
                is_vacant=row.is_vacant,
                market_value=_as_float(row.market_value),
                opportunity_score=row.opportunity_score,
                tags=list(row.tags or []),
                note=row.note,
                created_at=row.created_at,
                changes=[
                    WatchlistChange(code=c.code, label=c.label, severity=c.severity)
                    for c in changes
                ],
                has_alerts=len(changes) > 0,
            )
        )
    return items
