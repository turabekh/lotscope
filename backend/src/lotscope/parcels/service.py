from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.markets.models import Market
from lotscope.parcels.models import Parcel
from lotscope.parcels.schemas import ParcelDetail
from lotscope.zoning.service import resolve_district

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
    market = await session.get(Market, parcel.market_code)
    if market is not None and market.assessment_ratio is not None:
        detail.assessment_ratio = float(market.assessment_ratio)
    centroid = (
        await session.execute(_CENTROID_SQL, {"parcel_number": parcel_number})
    ).one_or_none()
    if centroid is not None:
        detail.longitude = centroid.longitude
        detail.latitude = centroid.latitude
    if parcel.base_zoning_code:
        detail.resolved_zoning_code = parcel.base_zoning_code
        detail.zoning_resolution = "attribute"
    elif parcel.resolved_zoning_code:
        detail.resolved_zoning_code = parcel.resolved_zoning_code
        detail.zoning_resolution = parcel.resolved_zoning_source or "spatial"
    else:
        resolution = await resolve_district(
            session, parcel_number, base_zoning_code=None, has_geometry=True
        )
        if resolution is not None:
            detail.resolved_zoning_code = resolution.code
            detail.zoning_resolution = resolution.method
    return detail


async def parcel_market_code(session: AsyncSession, parcel_number: str) -> str | None:
    market_code: str | None = await session.scalar(
        select(Parcel.market_code).where(Parcel.parcel_number == parcel_number)
    )
    return market_code
