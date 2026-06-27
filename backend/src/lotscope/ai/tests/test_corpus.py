from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.corpus import Title14Record, chunk_text, load_title14_documents, read_records
from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import vector_search


def test_chunk_text_handles_short_and_empty() -> None:
    assert chunk_text("hello") == ["hello"]
    assert chunk_text("   ") == []


def test_chunk_text_splits_long_text() -> None:
    chunks = chunk_text("x" * 4000, max_chars=1500, overlap=150)
    assert len(chunks) >= 3
    assert all(len(chunk) <= 1500 for chunk in chunks)


def test_read_records_parses_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "sections.jsonl"
    path.write_text(
        '{"section": "A", "text": "alpha"}\n\n{"section": "B", "title": "T", "text": "beta"}\n',
        encoding="utf-8",
    )
    records = read_records(path)
    assert [record.section for record in records] == ["A", "B"]
    assert records[1].title == "T"


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1) for _ in texts]


@pytest.mark.integration
async def test_load_title14_inserts_and_is_idempotent(db_session: AsyncSession) -> None:
    records = [
        Title14Record(section="14-701", title="RSA-5", text="x" * 3000),
        Title14Record(section="14-602", text="short section"),
    ]

    first = await load_title14_documents(db_session, records, _FakeEmbedder())
    await db_session.flush()
    assert first == 4

    count_after_first = await db_session.scalar(
        text("SELECT count(*) FROM document WHERE source = 'title14'")
    )
    await load_title14_documents(db_session, records, _FakeEmbedder())
    await db_session.flush()
    count_after_second = await db_session.scalar(
        text("SELECT count(*) FROM document WHERE source = 'title14'")
    )
    assert count_after_first == count_after_second

    results = await vector_search(
        db_session, [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1), limit=1, source="title14"
    )
    assert results[0].source == "title14"
