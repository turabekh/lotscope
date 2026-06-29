import json
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.embeddings import Embedder
from lotscope.ai.schemas import RetrievedDocument

_INSERT_SQL = text(
    "INSERT INTO document (source, section, title, content, doc_metadata, embedding) "
    "VALUES (:source, :section, :title, :content, (:metadata)::jsonb, (:embedding)::vector) "
    "RETURNING id"
)
_PARCEL_DEED_SQL = text(
    "SELECT id, source, section, title, content, "
    "(embedding <=> (:embedding)::vector) AS distance "
    "FROM document "
    "WHERE embedding IS NOT NULL AND source = :source "
    "AND doc_metadata->>'parcel_number' = :parcel_number "
    "ORDER BY distance ASC "
    "LIMIT :limit"
)
_SEARCH_SQL = text(
    "SELECT id, source, section, title, content, "
    "(embedding <=> (:embedding)::vector) AS distance "
    "FROM document "
    "WHERE embedding IS NOT NULL AND ((:source)::text IS NULL OR source = (:source)::text) "
    "ORDER BY distance ASC "
    "LIMIT :limit"
)
_DISTRICT_SQL = text(
    "SELECT id, source, section, title, content, 0.0 AS distance "
    "FROM document "
    "WHERE embedding IS NOT NULL AND ((:source)::text IS NULL OR source = (:source)::text) "
    "AND upper(regexp_replace(coalesce(substring(section from "
    r"'\(([^)]+)\)'"
    "), ''), '[^A-Za-z0-9.]', '', 'g')) "
    "= upper(regexp_replace(:district, '[^A-Za-z0-9.]', '', 'g')) "
    "ORDER BY id ASC "
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
    metadata: dict[str, object] | None = None,
) -> int:
    result = await session.execute(
        _INSERT_SQL,
        {
            "source": source,
            "section": section,
            "title": title,
            "content": content,
            "metadata": json.dumps(metadata or {}),
            "embedding": to_vector_literal(embedding),
        },
    )
    return int(result.scalar_one())


async def search_parcel_documents(
    session: AsyncSession,
    embedder: Embedder,
    query: str,
    parcel_number: str,
    *,
    source: str,
    limit: int = 3,
) -> list[RetrievedDocument]:
    vectors = await embedder.embed([query])
    rows = await session.execute(
        _PARCEL_DEED_SQL,
        {
            "embedding": to_vector_literal(vectors[0]),
            "source": source,
            "parcel_number": parcel_number,
            "limit": limit,
        },
    )
    return [
        RetrievedDocument(
            id=row.id,
            source=row.source,
            section=row.section,
            title=row.title,
            content=row.content,
            distance=float(row.distance),
        )
        for row in rows
    ]


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


async def fetch_district_documents(
    session: AsyncSession,
    district_code: str,
    *,
    limit: int = 2,
    source: str | None = None,
) -> list[RetrievedDocument]:
    rows = await session.execute(
        _DISTRICT_SQL, {"district": district_code, "source": source, "limit": limit}
    )
    return [
        RetrievedDocument(
            id=row.id,
            source=row.source,
            section=row.section,
            title=row.title,
            content=row.content,
            distance=float(row.distance),
        )
        for row in rows
    ]
