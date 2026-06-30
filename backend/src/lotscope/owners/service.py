from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.owners.schemas import OwnerParcel, OwnerPortfolio

MAX_PORTFOLIO_PARCELS = 50

_OWNER_SQL = text(
    "SELECT owner, owner_key, mailing_address FROM parcel WHERE parcel_number = :parcel_number"
)

_AGG_SQL = text(
    "SELECT count(*) AS total, "
    "count(*) FILTER (WHERE coalesce(is_vacant, false)) AS vacant, "
    "sum(market_value) AS total_value "
    "FROM parcel WHERE owner_key = :owner_key"
)

_LIST_SQL = text(
    "SELECT p.parcel_number, p.address, p.base_zoning_code, p.is_vacant, p.market_value, "
    "round(pv.opportunity_score)::int AS opportunity_score "
    "FROM parcel p LEFT JOIN parcel_verdict pv ON pv.parcel_number = p.parcel_number "
    "WHERE p.owner_key = :owner_key AND p.parcel_number <> :parcel_number "
    "ORDER BY p.market_value DESC NULLS LAST, p.parcel_number LIMIT :limit"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


def _owner_parcel(row: Row[Any]) -> OwnerParcel:
    return OwnerParcel(
        parcel_number=row.parcel_number,
        address=row.address,
        base_zoning_code=row.base_zoning_code,
        is_vacant=row.is_vacant,
        market_value=_as_float(row.market_value),
        opportunity_score=row.opportunity_score,
    )


async def get_owner_portfolio(session: AsyncSession, parcel_number: str) -> OwnerPortfolio | None:
    base = (await session.execute(_OWNER_SQL, {"parcel_number": parcel_number})).one_or_none()
    if base is None:
        return None
    owner = base.owner
    owner_key = base.owner_key
    if owner_key is None:
        return OwnerPortfolio(
            owner=owner,
            mailing_address=base.mailing_address,
            total_count=1,
            vacant_count=0,
            total_market_value=None,
            shown=0,
            parcels=[],
        )
    agg = (await session.execute(_AGG_SQL, {"owner_key": owner_key})).one()
    rows = (
        await session.execute(
            _LIST_SQL,
            {
                "owner_key": owner_key,
                "parcel_number": parcel_number,
                "limit": MAX_PORTFOLIO_PARCELS,
            },
        )
    ).all()
    parcels = [_owner_parcel(row) for row in rows]
    return OwnerPortfolio(
        owner=owner,
        mailing_address=base.mailing_address,
        total_count=int(agg.total or 0),
        vacant_count=int(agg.vacant or 0),
        total_market_value=_as_float(agg.total_value),
        shown=len(parcels),
        parcels=parcels,
    )
