from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.skiptrace.models import REASON_INVESTOR_GRANT
from lotscope.skiptrace.packs import INVESTOR_MONTHLY_CREDITS
from lotscope.skiptrace.service import grant_credits

_INVESTOR_IDS_SQL = text(
    "SELECT id FROM app_user WHERE tier = 'investor' AND is_active IS TRUE ORDER BY id"
)


async def grant_investor_credits(
    session_factory: async_sessionmaker[AsyncSession], *, month: str
) -> int:
    async with session_factory() as session:
        user_ids = [row[0] for row in await session.execute(_INVESTOR_IDS_SQL)]

    granted = 0
    for user_id in user_ids:
        async with session_factory() as session:
            if await grant_credits(
                session, user_id, INVESTOR_MONTHLY_CREDITS, REASON_INVESTOR_GRANT, month
            ):
                granted += 1
            await session.commit()
    return granted
