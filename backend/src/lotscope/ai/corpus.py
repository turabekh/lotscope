import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.embeddings import Embedder, VoyageEmbedder
from lotscope.ai.retrieval import to_vector_literal
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger

TITLE_14_SOURCE = "title14"
_MAX_CHARS = 1500
_OVERLAP = 150
_DEFAULT_PATH = Path("data/title14/sections.jsonl")

_DELETE_SOURCE = text("DELETE FROM document WHERE source = :source")
_INSERT = text(
    "INSERT INTO document (source, section, title, content, doc_metadata, embedding) "
    "VALUES (:source, :section, :title, :content, (:metadata)::jsonb, (:embedding)::vector)"
)


class Title14Record(BaseModel):
    section: str
    title: str | None = None
    text: str


def chunk_text(value: str, *, max_chars: int = _MAX_CHARS, overlap: int = _OVERLAP) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if len(cleaned) <= max_chars:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = start + max_chars
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = end - overlap
    return chunks


def read_records(path: Path) -> list[Title14Record]:
    records: list[Title14Record] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            records.append(Title14Record.model_validate_json(stripped))
    return records


async def load_title14_documents(
    session: AsyncSession,
    records: list[Title14Record],
    embedder: Embedder,
    *,
    source: str = TITLE_14_SOURCE,
) -> int:
    await session.execute(_DELETE_SOURCE, {"source": source})
    total = 0
    for record in records:
        chunks = chunk_text(record.text)
        if not chunks:
            continue
        vectors = await embedder.embed(chunks)
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
            await session.execute(
                _INSERT,
                {
                    "source": source,
                    "section": record.section,
                    "title": record.title,
                    "content": chunk,
                    "metadata": json.dumps({"chunk_index": index}),
                    "embedding": to_vector_literal(vector),
                },
            )
            total += 1
    return total


async def _run(path: Path) -> None:
    settings = get_settings()
    configure_logging(settings)
    records = read_records(path)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with VoyageEmbedder(settings) as embedder, session_factory() as session:
            count = await load_title14_documents(session, records, embedder)
            await session.commit()
            get_logger("ai.corpus").info("loaded_title14", documents=count, source=str(path))
    finally:
        await engine.dispose()


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_PATH
    asyncio.run(_run(path))


if __name__ == "__main__":
    main()
