from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.embeddings import Embedder
from lotscope.ai.schemas import RetrievedDocument

_INSERT_SQL = text(
    "INSERT INTO document (source, section, title, content, doc_metadata, embedding) "
    "VALUES (:source, :section, :title, :content, '{}'::jsonb, (:embedding)::vector) "
    "RETURNING id"
)
_SEARCH_SQL = text(
    "SELECT id, source, section, title, content, "
    "(embedding <=> (:embedding)::vector) AS distance "
    "FROM document "
    "WHERE embedding IS NOT NULL AND ((:source)::text IS NULL OR source = (:source)::text) "
    "ORDER BY distance ASC "
    "LIMIT :limit"
)


def to_vector_literal(embedding: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(value)) for value in embedding) + "]"


async def add_document(
    session: AsyncSession,
    *,
    source: str,
    content: str,
    embedding: Sequence[float],
    section: str | None = None,
    title: str | None = None,
) -> int:
    result = await session.execute(
        _INSERT_SQL,
        {
            "source": source,
            "section": section,
            "title": title,
            "content": content,
            "embedding": to_vector_literal(embedding),
        },
    )
    return int(result.scalar_one())


async def vector_search(
    session: AsyncSession,
    embedding: Sequence[float],
    *,
    limit: int = 5,
    source: str | None = None,
) -> list[RetrievedDocument]:
    rows = await session.execute(
        _SEARCH_SQL,
        {"embedding": to_vector_literal(embedding), "source": source, "limit": limit},
    )
    documents: list[RetrievedDocument] = []
    for row in rows:
        documents.append(
            RetrievedDocument(
                id=row.id,
                source=row.source,
                section=row.section,
                title=row.title,
                content=row.content,
                distance=float(row.distance),
            )
        )
    return documents


async def embed_and_search(
    session: AsyncSession,
    embedder: Embedder,
    query: str,
    *,
    limit: int = 5,
    source: str | None = None,
) -> list[RetrievedDocument]:
    vectors = await embedder.embed([query])
    return await vector_search(session, vectors[0], limit=limit, source=source)
