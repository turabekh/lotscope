from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.parcels.models import Parcel
from lotscope.parcels.schemas import ParcelDetail

_CENTROID_SQL = text(
    "SELECT ST_X(ST_Centroid(geom_4326)) AS longitude, "
    "ST_Y(ST_Centroid(geom_4326)) AS latitude "
    "FROM parcel WHERE parcel_number = :parcel_number AND geom_4326 IS NOT NULL"
)


async def get_parcel_detail(session: AsyncSession, parcel_number: str) -> ParcelDetail | None:
    parcel = await session.get(Parcel, parcel_number)
    if parcel is None:
        return None
    detail = ParcelDetail.model_validate(parcel)
    centroid = (
        await session.execute(_CENTROID_SQL, {"parcel_number": parcel_number})
    ).one_or_none()
    if centroid is not None:
        detail.longitude = centroid.longitude
        detail.latitude = centroid.latitude
    return detail
