from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.provisions.schemas import ProvisionRead
from lotscope.provisions.service import (
    ancestors_of,
    children_of,
    search_ranked,
)

PHILADELPHIA_MARKET_CODE = "phl"
DEFAULT_TITLE_SCOPE = ("14",)
LEXICAL_LIMIT = 12
SECTION_KINDS = frozenset({"section", "chapter", "title"})


@dataclass(frozen=True)
class Candidate:
    provision_id: str
    cite: str
    origin: str


async def lexical_candidates(
    session: AsyncSession,
    query: str,
    *,
    market_code: str = PHILADELPHIA_MARKET_CODE,
    title_numbers: list[str] | None = None,
    limit: int = LEXICAL_LIMIT,
) -> list[Candidate]:
    scope = list(title_numbers) if title_numbers is not None else list(DEFAULT_TITLE_SCOPE)
    found = await search_ranked(
        session, market_code, query, title_numbers=scope or None, limit=limit
    )
    return [Candidate(provision_id=row.id, cite=row.cite, origin="lexical") for row in found]


async def expand_to_section_window(
    session: AsyncSession,
    provision_id: str,
    *,
    market_code: str = PHILADELPHIA_MARKET_CODE,
) -> list[ProvisionRead]:
    chain = await ancestors_of(session, market_code, provision_id)
    section = next(
        (item for item in reversed(chain) if item.kind in SECTION_KINDS),
        None,
    )
    if section is None:
        return []
    return await children_of(session, market_code, section.id)


def merge_candidates(
    lexical: list[Candidate], vector: list[Candidate], *, limit: int
) -> list[Candidate]:
    merged: list[Candidate] = []
    seen: set[str] = set()
    for candidate in [*lexical, *vector]:
        if candidate.provision_id in seen:
            continue
        seen.add(candidate.provision_id)
        merged.append(candidate)
        if len(merged) >= limit:
            break
    return merged
