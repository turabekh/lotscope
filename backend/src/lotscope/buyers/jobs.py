from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.buyers.service import recompute_buyer_profiles

BUYER_MARKETS = ("phl",)


async def recompute_all_buyers(session_factory: async_sessionmaker[AsyncSession]) -> int:
    total = 0
    async with session_factory() as session:
        for market in BUYER_MARKETS:
            total += await recompute_buyer_profiles(session, market_code=market)
        await session.commit()
    return total
