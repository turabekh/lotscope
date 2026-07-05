from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.markets.models import Market


async def list_markets(session: AsyncSession) -> list[Market]:
    result = await session.execute(select(Market).order_by(Market.name))
    return list(result.scalars())
