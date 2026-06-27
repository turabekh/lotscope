import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.search.schemas import ParcelSearchResult

_NON_DIGIT = re.compile(r"\D")
_MAX_LIMIT = 50
_ACCOUNT_LENGTH = 9

_SEARCH_SQL = text(
    """
    SELECT parcel_number, address, owner,
           GREATEST(
               similarity(coalesce(address, ''), :query),
               similarity(coalesce(owner, ''), :query)
           ) AS score
    FROM parcel
    WHERE address ILIKE :contains
       OR owner ILIKE :contains
       OR parcel_number = :query
       OR parcel_number = :padded
       OR parcel_number LIKE :prefix
    ORDER BY
        (parcel_number = :query OR parcel_number = :padded) DESC,
        score DESC,
        parcel_number
    LIMIT :limit OFFSET :offset
    """
)


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _padded_account(query: str) -> str:
    digits = _NON_DIGIT.sub("", query)
    if digits and len(digits) <= _ACCOUNT_LENGTH:
        return digits.zfill(_ACCOUNT_LENGTH)
    return ""


async def search_parcels(
    session: AsyncSession, query: str, *, limit: int = 20, offset: int = 0
) -> list[ParcelSearchResult]:
    cleaned = query.strip()
    if not cleaned:
        return []
    escaped = _like_escape(cleaned)
    result = await session.execute(
        _SEARCH_SQL,
        {
            "query": cleaned,
            "contains": f"%{escaped}%",
            "prefix": f"{escaped}%",
            "padded": _padded_account(cleaned),
            "limit": max(1, min(limit, _MAX_LIMIT)),
            "offset": max(0, offset),
        },
    )
    return [
        ParcelSearchResult(
            parcel_number=row.parcel_number,
            address=row.address,
            owner=row.owner,
            score=float(row.score or 0.0),
        )
        for row in result
    ]
