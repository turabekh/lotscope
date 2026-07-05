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
_EMBED_BATCH = 96
_DEFAULT_PATH = Path("data/title14/sections.jsonl")

_DELETE_SOURCE = text("DELETE FROM document WHERE source = :source")
_DELETE_SOURCE_MARKET = text(
    "DELETE FROM document WHERE source = :source AND doc_metadata->>'market' = :market"
)
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
    market: str | None = None,
) -> int:
    if market is None:
        await session.execute(_DELETE_SOURCE, {"source": source})
    else:
        await session.execute(_DELETE_SOURCE_MARKET, {"source": source, "market": market})
    items: list[tuple[Title14Record, int, str]] = []
    for record in records:
        for index, chunk in enumerate(chunk_text(record.text)):
            items.append((record, index, chunk))
    if not items:
        return 0
    vectors: list[list[float]] = []
    for start in range(0, len(items), _EMBED_BATCH):
        batch = [chunk for _, _, chunk in items[start : start + _EMBED_BATCH]]
        vectors.extend(await embedder.embed(batch))
    for (record, index, chunk), vector in zip(items, vectors, strict=True):
        metadata: dict[str, object] = {"chunk_index": index}
        if market is not None:
            metadata["market"] = market
        await session.execute(
            _INSERT,
            {
                "source": source,
                "section": record.section,
                "title": record.title,
                "content": chunk,
                "metadata": json.dumps(metadata),
                "embedding": to_vector_literal(vector),
            },
        )
    return len(items)


async def _run(path: Path, *, source: str = TITLE_14_SOURCE, market: str | None = None) -> None:
    settings = get_settings()
    configure_logging(settings)
    records = read_records(path)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        async with VoyageEmbedder(settings) as embedder, session_factory() as session:
            count = await load_title14_documents(
                session, records, embedder, source=source, market=market
            )
            await session.commit()
            get_logger("ai.corpus").info(
                "loaded_corpus", documents=count, source=source, market=market, path=str(path)
            )
    finally:
        await engine.dispose()


def main() -> None:
    args = sys.argv[1:]
    source = TITLE_14_SOURCE
    market: str | None = None
    if "--source" in args:
        i = args.index("--source")
        source = args[i + 1]
        del args[i : i + 2]
    if "--market" in args:
        i = args.index("--market")
        market = args[i + 1]
        del args[i : i + 2]
    path = Path(args[0]) if args else _DEFAULT_PATH
    asyncio.run(_run(path, source=source, market=market))


if __name__ == "__main__":
    main()
