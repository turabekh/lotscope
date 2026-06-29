from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.neighborhoods.models import Neighborhood
from lotscope.neighborhoods.schemas import NeighborhoodSummary


async def list_neighborhoods(session: AsyncSession) -> list[NeighborhoodSummary]:
    rows = (
        await session.execute(
            select(distinct(Neighborhood.name))
            .where(Neighborhood.name.isnot(None))
            .order_by(Neighborhood.name)
        )
    ).all()
    return [NeighborhoodSummary(name=row[0]) for row in rows]
