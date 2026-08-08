from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.models import CodeProvision
from lotscope.provisions.schemas import ProvisionRead


async def title_numbers(session: AsyncSession, market_code: str) -> list[str]:
    statement = (
        select(distinct(CodeProvision.title_number))
        .where(CodeProvision.market_code == market_code)
        .order_by(CodeProvision.title_number)
    )
    return list((await session.execute(statement)).scalars())


async def provisions_for_title(
    session: AsyncSession, market_code: str, title_number: str
) -> list[ProvisionRead]:
    statement = (
        select(CodeProvision)
        .where(
            CodeProvision.market_code == market_code,
            CodeProvision.title_number == title_number,
        )
        .order_by(CodeProvision.ordinal)
    )
    rows = (await session.execute(statement)).scalars()
    return [ProvisionRead.model_validate(row, from_attributes=True) for row in rows]


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
