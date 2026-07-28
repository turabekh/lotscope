from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.buyers.service import recompute_buyer_profiles
from lotscope.core.logging import get_logger

BUYER_MARKETS = ("phl",)


async def recompute_all_buyers(
    session_factory: async_sessionmaker[AsyncSession], *, market: str | None = None
) -> int:
    targets = tuple(m for m in BUYER_MARKETS if market is None or m == market)
    if not targets:
        get_logger("buyers.jobs").info(
            "buyer_recompute_skipped", market=market, buyer_markets=list(BUYER_MARKETS)
        )
        return 0
    total = 0
    async with session_factory() as session:
        for target in targets:
            total += await recompute_buyer_profiles(session, market_code=target)
        await session.commit()
    return total
