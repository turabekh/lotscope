from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.compare.schemas import ParcelCompareItem, ParcelCompareResponse
from lotscope.parcels.service import get_parcel_detail
from lotscope.verdict.service import get_verdict

MAX_COMPARE_PARCELS = 4


def dedupe_preserve_order(parcel_numbers: Sequence[str], limit: int) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for parcel_number in parcel_numbers:
        if parcel_number in seen:
            continue
        seen.add(parcel_number)
        ordered.append(parcel_number)
        if len(ordered) >= limit:
            break
    return ordered


async def compare_parcels(
    session: AsyncSession, parcel_numbers: Sequence[str], *, limit: int = MAX_COMPARE_PARCELS
) -> ParcelCompareResponse:
    items: list[ParcelCompareItem] = []
    for parcel_number in dedupe_preserve_order(parcel_numbers, limit):
        detail = await get_parcel_detail(session, parcel_number)
        if detail is None:
            continue
        verdict = await get_verdict(session, parcel_number)
        items.append(ParcelCompareItem(detail=detail, verdict=verdict))
    await session.commit()
    return ParcelCompareResponse(items=items)
