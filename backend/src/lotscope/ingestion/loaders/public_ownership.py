from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ingestion.service import record_freshness
from lotscope.parcels.models import Parcel
from lotscope.parcels.public_ownership import is_public_owner

PUBLIC_OWNERSHIP_DATASET = "opa_derived_public_ownership"
_MARKET = "phl"

_PUBLIC_OWNERSHIP_UPDATE = text(
    "UPDATE parcel SET is_city_owned = :is_public "
    "WHERE parcel_number = :parcel_number AND market_code = 'phl' "
    "AND coalesce(is_city_owned, false) IS DISTINCT FROM :is_public"
)


async def derive_phl_public_ownership(session: AsyncSession) -> int:
    result = await session.execute(
        select(Parcel.parcel_number, Parcel.owner, Parcel.is_city_owned).where(
            Parcel.market_code == _MARKET
        )
    )
    updates: list[dict[str, Any]] = []
    for row in result:
        is_public = is_public_owner(row.owner)
        if bool(row.is_city_owned) is not is_public:
            updates.append({"parcel_number": row.parcel_number, "is_public": is_public})
    if updates:
        await session.execute(_PUBLIC_OWNERSHIP_UPDATE, updates)
    await record_freshness(
        session,
        PUBLIC_OWNERSHIP_DATASET,
        status="success",
        success=True,
        market_code=_MARKET,
        row_count=len(updates),
    )
    return len(updates)
