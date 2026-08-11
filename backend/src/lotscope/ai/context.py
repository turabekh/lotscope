from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.retrieval import fetch_documents_by_cite
from lotscope.ai.schemas import RetrievedDocument
from lotscope.ai.scope import RetrievalScope
from lotscope.provisions.service import (
    ancestors_of,
    children_of,
    descendants_of,
    get_provision,
    refs_of,
)

MAX_CONTEXT_CHARS = 24_000
MAX_WINDOWS = 3
MAX_PROVISIONS_PER_WINDOW = 12
MAX_REFS_PER_HIT = 3
SECTION_KINDS = frozenset({"section", "chapter", "title"})
TABLE_KIND = "table"


@dataclass(frozen=True)
class ContextBudget:
    max_chars: int = MAX_CONTEXT_CHARS


def dedupe(documents: list[RetrievedDocument]) -> list[RetrievedDocument]:
    seen: set[int] = set()
    unique: list[RetrievedDocument] = []
    for document in documents:
        if document.id in seen:
            continue
        seen.add(document.id)
        unique.append(document)
    return unique


def fit_to_budget(
    documents: list[RetrievedDocument], budget: ContextBudget
) -> list[RetrievedDocument]:
    kept: list[RetrievedDocument] = []
    spent = 0
    for document in dedupe(documents):
        cost = len(document.content)
        if kept and spent + cost > budget.max_chars:
            break
        kept.append(document)
        spent += cost
    return kept


async def section_window_cites(
    session: AsyncSession,
    provision_id: str,
    *,
    market_code: str,
    max_provisions: int = MAX_PROVISIONS_PER_WINDOW,
) -> list[str]:
    provision = await get_provision(session, market_code, provision_id)
    if provision is None:
        return []
    if provision.kind in SECTION_KINDS:
        section = provision
    else:
        chain = await ancestors_of(session, market_code, provision_id)
        found = next((item for item in reversed(chain) if item.kind in SECTION_KINDS), None)
        if found is None:
            return []
        section = found

    tables = await descendants_of(
        session, market_code, section.id, kinds=[TABLE_KIND], limit=max_provisions
    )
    children = await children_of(session, market_code, section.id)
    cites = [section.cite]
    for item in [*tables, *children]:
        if len(cites) >= max_provisions:
            break
        if item.cite not in cites:
            cites.append(item.cite)
    return cites


async def expand_refs(
    session: AsyncSession,
    hits: list[RetrievedDocument],
    *,
    market_code: str,
    scope: RetrievalScope,
    max_refs: int = MAX_REFS_PER_HIT,
) -> list[RetrievedDocument]:
    attribution: dict[str, str] = {}
    for hit in hits:
        if hit.section is None:
            continue
        referenced = await refs_of(session, market_code, hit.section)
        for provision in referenced[:max_refs]:
            attribution.setdefault(provision.cite, hit.section)
    if not attribution:
        return []
    documents = await fetch_documents_by_cite(
        session,
        list(attribution),
        limit=len(attribution),
        source=scope.source,
        market=scope.market,
        titles=scope.titles,
    )
    return [
        document.model_copy(update={"via": attribution.get(document.section or "")})
        for document in documents
    ]


async def expand_to_windows(
    session: AsyncSession,
    hits: list[RetrievedDocument],
    *,
    market_code: str,
    scope: RetrievalScope,
    max_windows: int = MAX_WINDOWS,
    max_provisions: int = MAX_PROVISIONS_PER_WINDOW,
) -> list[RetrievedDocument]:
    cites: list[str] = []
    for hit in hits[:max_windows]:
        if hit.section is None:
            continue
        window = await section_window_cites(
            session, hit.section, market_code=market_code, max_provisions=max_provisions
        )
        for cite in window:
            if cite not in cites:
                cites.append(cite)
    if not cites:
        return []
    return await fetch_documents_by_cite(
        session,
        cites,
        limit=max_windows * max_provisions,
        source=scope.source,
        market=scope.market,
        titles=scope.titles,
    )
