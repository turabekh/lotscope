from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.parcels.models import Parcel
from lotscope.parcels.schemas import ParcelDetail


async def get_parcel_detail(session: AsyncSession, parcel_number: str) -> ParcelDetail | None:
    parcel = await session.get(Parcel, parcel_number)
    if parcel is None:
        return None
    return ParcelDetail.model_validate(parcel)
