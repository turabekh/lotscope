import asyncio
import json

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.derivation import (
    DERIVATION_VERSION,
    PHILLYCODE_SOURCE,
    DerivedDocument,
    SourceProvision,
    derive,
)
from lotscope.ai.embeddings import Embedder
from lotscope.ai.errors import EmbeddingError
from lotscope.ai.retrieval import to_vector_literal
from lotscope.core.logging import get_logger
from lotscope.provisions.service import provisions_for_title, title_numbers

PHILADELPHIA_MARKET_CODE = "phl"
_EMBED_BATCH = 96
DEFAULT_BATCH_CHARS = 48_000


def batch_documents(
    documents: list[DerivedDocument],
    *,
    max_items: int = _EMBED_BATCH,
    max_chars: int = DEFAULT_BATCH_CHARS,
) -> list[list[DerivedDocument]]:
    batches: list[list[DerivedDocument]] = []
    current: list[DerivedDocument] = []
    budget = 0
    for document in documents:
        size = len(document.content)
        if current and (len(current) >= max_items or budget + size > max_chars):
            batches.append(current)
            current, budget = [], 0
        current.append(document)
        budget += size
    if current:
        batches.append(current)
    return batches


logger = get_logger(__name__)

_UPSERT = text(
    "INSERT INTO document (source, section, title, content, doc_metadata, embedding) "
    "VALUES (:source, :section, :title, :content, (:metadata)::jsonb, (:embedding)::vector) "
    "ON CONFLICT (source, (doc_metadata->>'provision_id')) "
    "WHERE doc_metadata ? 'provision_id' "
    "DO UPDATE SET section = EXCLUDED.section, title = EXCLUDED.title, "
    "content = EXCLUDED.content, doc_metadata = EXCLUDED.doc_metadata, "
    "embedding = EXCLUDED.embedding, updated_at = now()"
)
_EXISTING_FOR_TITLE = text(
    "SELECT doc_metadata->>'provision_id' AS provision_id FROM document "
    "WHERE source = :source AND doc_metadata->>'title_number' = :title_number"
)
_PRUNE = text(
    "DELETE FROM document WHERE source = :source "
    "AND doc_metadata->>'title_number' = :title_number "
    "AND doc_metadata->>'provision_id' = ANY(:stale)"
)


class TitleDerivationResult(BaseModel):
    title_number: str
    error: str | None = None
    documents: int
    table_documents: int
    skipped_continuations: int
    skipped_figures: int
    skipped_notes: int
    skipped_containers: int
    folded_leaves: int
    pruned: int
    provisions_seen: int
    reconciled: bool


class DerivationRunReport(BaseModel):
    source: str
    derivation_version: str
    source_version: str | None
    results: list[TitleDerivationResult]

    @property
    def documents(self) -> int:
        return sum(result.documents for result in self.results)

    @property
    def table_documents(self) -> int:
        return sum(result.table_documents for result in self.results)

    @property
    def skipped_continuations(self) -> int:
        return sum(result.skipped_continuations for result in self.results)

    @property
    def provisions_seen(self) -> int:
        return sum(result.provisions_seen for result in self.results)

    @property
    def reconciled(self) -> bool:
        return all(result.reconciled for result in self.results)

    @property
    def failed_titles(self) -> list[str]:
        return [result.title_number for result in self.results if result.error]


def _metadata(document: DerivedDocument, derivation_version: str) -> str:
    return json.dumps(
        {
            "provision_id": document.provision_id,
            "cite": document.cite,
            "title_number": document.title_number,
            "kind": document.kind,
            "path": document.path,
            "source_version": document.source_version,
            "derivation_version": derivation_version,
            "folded_provision_ids": document.folded_provision_ids,
        }
    )


async def derive_title(
    session: AsyncSession,
    embedder: Embedder,
    title_number: str,
    *,
    market_code: str = PHILADELPHIA_MARKET_CODE,
    derivation_version: str = DERIVATION_VERSION,
    max_batch_chars: int = DEFAULT_BATCH_CHARS,
    pace_seconds: float = 0.0,
) -> TitleDerivationResult:
    rows = await provisions_for_title(session, market_code, title_number)
    provisions = [
        SourceProvision(
            id=row.id,
            cite=row.cite,
            kind=row.kind,
            title_number=row.title_number,
            parent=row.parent,
            ordinal=row.ordinal,
            path=row.path,
            heading=row.heading,
            text=row.text,
            source_version=row.source_version,
            table_data=row.table_data,
        )
        for row in rows
    ]
    documents, report = derive(provisions)

    vectors: list[list[float]] = []
    for index, batch in enumerate(batch_documents(documents, max_chars=max_batch_chars)):
        if index and pace_seconds:
            await asyncio.sleep(pace_seconds)
        vectors.extend(await embedder.embed([document.content for document in batch]))

    for document, vector in zip(documents, vectors, strict=True):
        await session.execute(
            _UPSERT,
            {
                "source": PHILLYCODE_SOURCE,
                "section": document.cite,
                "title": document.heading,
                "content": document.content,
                "metadata": _metadata(document, derivation_version),
                "embedding": to_vector_literal(vector),
            },
        )

    keep = {document.provision_id for document in documents}
    existing = set(
        (
            await session.execute(
                _EXISTING_FOR_TITLE,
                {"source": PHILLYCODE_SOURCE, "title_number": title_number},
            )
        )
        .scalars()
        .all()
    )
    stale = sorted(existing - keep)
    if stale:
        await session.execute(
            _PRUNE,
            {
                "source": PHILLYCODE_SOURCE,
                "title_number": title_number,
                "stale": stale,
            },
        )

    return TitleDerivationResult(
        title_number=title_number,
        documents=report.documents,
        table_documents=report.table_documents,
        skipped_continuations=report.skipped_continuations,
        skipped_figures=report.skipped_figures,
        skipped_notes=report.skipped_notes,
        skipped_containers=report.skipped_containers,
        folded_leaves=report.folded_leaves,
        pruned=len(stale),
        provisions_seen=report.provisions_seen,
        reconciled=report.reconciles(),
    )


async def derive_corpus(
    session: AsyncSession,
    embedder: Embedder,
    *,
    market_code: str = PHILADELPHIA_MARKET_CODE,
    titles: list[str] | None = None,
    derivation_version: str = DERIVATION_VERSION,
    max_batch_chars: int = DEFAULT_BATCH_CHARS,
    pace_seconds: float = 0.0,
) -> DerivationRunReport:
    wanted = titles if titles is not None else await title_numbers(session, market_code)
    results: list[TitleDerivationResult] = []
    for title_number in wanted:
        try:
            result = await derive_title(
                session,
                embedder,
                title_number,
                market_code=market_code,
                derivation_version=derivation_version,
                max_batch_chars=max_batch_chars,
                pace_seconds=pace_seconds,
            )
            await session.commit()
        except EmbeddingError as error:
            await session.rollback()
            logger.error(
                "phillycode_derivation_title_failed",
                title_number=title_number,
                error=str(error),
            )
            result = TitleDerivationResult(
                title_number=title_number,
                error=str(error),
                documents=0,
                table_documents=0,
                skipped_continuations=0,
                skipped_figures=0,
                skipped_notes=0,
                skipped_containers=0,
                folded_leaves=0,
                pruned=0,
                provisions_seen=0,
                reconciled=False,
            )
        results.append(result)
    source_version = None
    for title_number in wanted:
        rows = await provisions_for_title(session, market_code, title_number)
        if rows:
            source_version = rows[0].source_version
            break

    report = DerivationRunReport(
        source=PHILLYCODE_SOURCE,
        derivation_version=derivation_version,
        source_version=source_version,
        results=results,
    )
    logger.info(
        "phillycode_derivation",
        source_version=report.source_version,
        derivation_version=derivation_version,
        titles=len(results),
        documents=report.documents,
        table_documents=report.table_documents,
        skipped_continuations=report.skipped_continuations,
        provisions_seen=report.provisions_seen,
        reconciled=report.reconciled,
    )
    return report
