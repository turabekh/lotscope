from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.watchlist.models import SavedParcel
from lotscope.watchlist.schemas import SavedParcelCreate, SavedParcelUpdate, WatchlistItem

_PARCEL_EXISTS_SQL = text("SELECT 1 FROM parcel WHERE parcel_number = :parcel_number")
_LIST_SQL = text(
    "SELECT sp.parcel_number, sp.tags, sp.note, sp.created_at, "
    "p.address, p.owner, p.base_zoning_code, p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score "
    "FROM saved_parcel sp "
    "JOIN parcel p ON p.parcel_number = sp.parcel_number "
    "LEFT JOIN parcel_verdict pv ON pv.parcel_number = sp.parcel_number "
    "WHERE sp.user_id = :user_id ORDER BY sp.created_at DESC"
)


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
    exists = await session.scalar(_PARCEL_EXISTS_SQL, {"parcel_number": data.parcel_number})
    if not exists:
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


async def remove_saved(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    item = await session.get(SavedParcel, (user_id, parcel_number))
    if item is None:
        return False
    await session.delete(item)
    await session.flush()
    return True


async def list_saved(session: AsyncSession, user_id: int) -> list[WatchlistItem]:
    rows = (await session.execute(_LIST_SQL, {"user_id": user_id})).all()
    return [
        WatchlistItem(
            parcel_number=row.parcel_number,
            address=row.address,
            owner=row.owner,
            base_zoning_code=row.base_zoning_code,
            is_vacant=row.is_vacant,
            market_value=float(row.market_value) if row.market_value is not None else None,
            opportunity_score=row.opportunity_score,
            tags=list(row.tags or []),
            note=row.note,
            created_at=row.created_at,
        )
        for row in rows
    ]
