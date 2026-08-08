from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.models import CodeProvision


async def find_by_cite(session: AsyncSession, market_code: str, cite: str) -> list[CodeProvision]:
    statement = (
        select(CodeProvision)
        .where(CodeProvision.market_code == market_code, CodeProvision.cite == cite)
        .order_by(CodeProvision.title_number, CodeProvision.ordinal, CodeProvision.id)
    )
    return list((await session.execute(statement)).scalars())


async def children_of(
    session: AsyncSession, market_code: str, parent_id: str
) -> list[CodeProvision]:
    statement = (
        select(CodeProvision)
        .where(CodeProvision.market_code == market_code, CodeProvision.parent == parent_id)
        .order_by(CodeProvision.ordinal, CodeProvision.id)
    )
    return list((await session.execute(statement)).scalars())
