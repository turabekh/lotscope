from sqlalchemy import Select, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.models import CodeProvision
from lotscope.provisions.schemas import ProvisionRead

MAX_ANCESTOR_DEPTH = 12


def _read(row: CodeProvision) -> ProvisionRead:
    return ProvisionRead.model_validate(row, from_attributes=True)


async def _fetch(
    session: AsyncSession, statement: Select[tuple[CodeProvision]]
) -> list[ProvisionRead]:
    return [_read(row) for row in (await session.execute(statement)).scalars()]


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
    return await _fetch(
        session,
        select(CodeProvision)
        .where(
            CodeProvision.market_code == market_code,
            CodeProvision.title_number == title_number,
        )
        .order_by(CodeProvision.ordinal),
    )


async def get_provision(
    session: AsyncSession, market_code: str, provision_id: str
) -> ProvisionRead | None:
    row = await session.get(CodeProvision, {"market_code": market_code, "id": provision_id})
    return _read(row) if row is not None else None


async def find_by_cite(session: AsyncSession, market_code: str, cite: str) -> list[ProvisionRead]:
    return await _fetch(
        session,
        select(CodeProvision)
        .where(CodeProvision.market_code == market_code, CodeProvision.cite == cite)
        .order_by(CodeProvision.title_number, CodeProvision.ordinal, CodeProvision.id),
    )


async def children_of(
    session: AsyncSession, market_code: str, parent_id: str
) -> list[ProvisionRead]:
    return await _fetch(
        session,
        select(CodeProvision)
        .where(CodeProvision.market_code == market_code, CodeProvision.parent == parent_id)
        .order_by(CodeProvision.ordinal, CodeProvision.id),
    )


async def ancestors_of(
    session: AsyncSession, market_code: str, provision_id: str
) -> list[ProvisionRead]:
    provision = await get_provision(session, market_code, provision_id)
    if provision is None:
        return []
    chain: list[ProvisionRead] = []
    seen = {provision_id}
    parent = provision.parent
    while parent is not None and parent not in seen and len(chain) < MAX_ANCESTOR_DEPTH:
        seen.add(parent)
        ancestor = await get_provision(session, market_code, parent)
        if ancestor is None:
            break
        chain.append(ancestor)
        parent = ancestor.parent
    return list(reversed(chain))


async def siblings_of(
    session: AsyncSession, market_code: str, provision_id: str
) -> list[ProvisionRead]:
    provision = await get_provision(session, market_code, provision_id)
    if provision is None or provision.parent is None:
        return []
    return [
        sibling
        for sibling in await children_of(session, market_code, provision.parent)
        if sibling.id != provision_id
    ]


async def refs_of(
    session: AsyncSession, market_code: str, provision_id: str
) -> list[ProvisionRead]:
    provision = await get_provision(session, market_code, provision_id)
    if provision is None or not provision.refs:
        return []
    resolved = await _fetch(
        session,
        select(CodeProvision)
        .where(CodeProvision.market_code == market_code, CodeProvision.cite.in_(provision.refs))
        .order_by(CodeProvision.title_number, CodeProvision.ordinal, CodeProvision.id),
    )
    return [row for row in resolved if row.id != provision_id]
