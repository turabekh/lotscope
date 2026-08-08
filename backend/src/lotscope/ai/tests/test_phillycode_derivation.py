import json
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.phillycode import derive_corpus, derive_title

pytestmark = pytest.mark.integration


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0
        self.texts: list[str] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        self.texts.extend(texts)
        return [[0.01] * EMBEDDING_DIMENSIONS for _ in texts]


_INSERT = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES (:market_code, :id, :cite, 'code', :kind, "
    ":title_number, :parent, :ordinal, (:path)::jsonb, :heading, :text, :text, '[]'::jsonb, "
    "'[]'::jsonb, (:table_data)::jsonb, 1, 1, 'x.pdf', 'May 25, 2026')"
)

LONG = (
    "A provision long enough that it stands as its own document rather than folding into "
    "a parent, which needs more than one hundred and twenty characters of body text."
)


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("14", "14", "title", None, 1, ["14"], "Title 14", ""),
        ("14-800", "14-800", "chapter", "14", 2, ["14", "14-800"], "PARKING AND LOADING", ""),
        (
            "14-802",
            "14-802",
            "section",
            "14-800",
            3,
            ["14", "14-800", "14-802"],
            "Motor Vehicle Parking Ratios.",
            LONG,
        ),
        (
            "14-802(1)",
            "14-802(1)",
            "subsection",
            "14-802",
            4,
            ["14", "14-800", "14-802", "(1)"],
            None,
            "Short.",
        ),
        (
            "14-802#table1",
            "14-802#table1",
            "table",
            "14-802",
            5,
            ["14", "14-800", "14-802"],
            None,
            "rows",
        ),
        (
            "14-802#figure1",
            "14-802#figure1",
            "figure",
            "14-802",
            6,
            ["14", "14-800", "14-802"],
            None,
            "For printable PDF version, click HERE",
        ),
    ]
    table_payload = json.dumps(
        {
            "caption": "Table 14-802-3: Required Parking in Industrial Districts",
            "continuation_of": None,
            "header_rows": [],
            "rows": [[None, "IRMX", "ICMX I-1"], ["Household Living", "3/10 units", "1/2 units"]],
        }
    )
    for identifier, cite, kind, parent, ordinal, path, heading, body in rows:
        await session.execute(
            _INSERT,
            {
                "market_code": "phl",
                "id": identifier,
                "cite": cite,
                "kind": kind,
                "title_number": "14",
                "parent": parent,
                "ordinal": ordinal,
                "path": json.dumps(path),
                "heading": heading,
                "text": body,
                "table_data": table_payload if kind == "table" else None,
            },
        )
    await session.flush()


async def _documents(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await session.execute(
        text(
            "SELECT section, content, doc_metadata FROM document "
            "WHERE source = 'phillycode' ORDER BY section"
        )
    )
    return [{"section": r[0], "content": r[1], "metadata": r[2]} for r in rows]


async def test_derivation_emits_prose_and_table_documents(db_session: AsyncSession) -> None:
    await _seed(db_session)
    embedder = FakeEmbedder()

    result = await derive_title(db_session, embedder, "14")

    assert result.table_documents == 1
    assert result.skipped_figures == 1
    assert result.folded_leaves == 1
    assert result.skipped_containers == 1
    assert result.documents == 3
    assert result.provisions_seen == 6
    assert result.reconciled is True


async def test_every_document_carries_its_provenance(db_session: AsyncSession) -> None:
    await _seed(db_session)

    await derive_title(db_session, FakeEmbedder(), "14")

    documents = await _documents(db_session)
    assert [d["section"] for d in documents] == ["14-800", "14-802", "14-802#table1"]
    metadata = next(d["metadata"] for d in documents if d["section"] == "14-802")
    assert metadata["provision_id"] == "14-802"
    assert metadata["cite"] == "14-802"
    assert metadata["title_number"] == "14"
    assert metadata["kind"] == "section"
    assert metadata["path"] == ["14", "14-800", "14-802"]
    assert metadata["source_version"] == "May 25, 2026"
    assert metadata["derivation_version"] == "d2"
    assert metadata["folded_provision_ids"] == ["14-802(1)"]


async def test_a_table_node_becomes_a_linearised_document(db_session: AsyncSession) -> None:
    await _seed(db_session)

    await derive_title(db_session, FakeEmbedder(), "14")

    documents = await _documents(db_session)
    table = next(d for d in documents if d["metadata"]["kind"] == "table")
    assert "Table 14-802-3" in table["content"]


async def test_the_embedded_content_carries_the_ancestor_prefix(db_session: AsyncSession) -> None:
    await _seed(db_session)
    embedder = FakeEmbedder()

    await derive_title(db_session, embedder, "14")

    embedded = next(t for t in embedder.texts if "Motor Vehicle Parking Ratios" in t)
    assert embedded.startswith(
        "Philadelphia Code, Title 14 > 14-800 (PARKING AND LOADING) "
        "> 14-802 (Motor Vehicle Parking Ratios) > 14-802"
    )
    assert "14-802(1) Short." in embedded


async def test_re_deriving_updates_in_place_rather_than_duplicating(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await derive_title(db_session, FakeEmbedder(), "14")
    first = await _documents(db_session)

    result = await derive_title(db_session, FakeEmbedder(), "14")
    second = await _documents(db_session)

    assert result.documents == 3
    assert len(second) == len(first) == 3
    assert [d["content"] for d in second] == [d["content"] for d in first]


async def test_a_provision_removed_upstream_has_its_document_pruned(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await derive_title(db_session, FakeEmbedder(), "14")

    await db_session.execute(
        text("DELETE FROM code_provision WHERE id = '14-800' AND market_code = 'phl'")
    )
    await db_session.execute(
        text("UPDATE code_provision SET parent = '14' WHERE id = '14-802' AND market_code='phl'")
    )
    result = await derive_title(db_session, FakeEmbedder(), "14")

    assert result.pruned == 1
    assert [d["section"] for d in await _documents(db_session)] == ["14-802", "14-802#table1"]


async def test_the_run_report_reconciles_across_titles(db_session: AsyncSession) -> None:
    await _seed(db_session)

    report = await derive_corpus(db_session, FakeEmbedder(), titles=["14"])

    assert report.reconciled is True
    assert report.documents == 3
    assert report.table_documents == 1
    assert report.provisions_seen == 6
    assert report.source_version == "May 25, 2026"


async def test_the_incumbent_title14_source_is_never_touched(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await db_session.execute(
        text(
            "INSERT INTO document (source, section, title, content, doc_metadata) "
            "VALUES ('title14', '14-701', 'Quick Guide', 'incumbent text', '{}'::jsonb)"
        )
    )

    await derive_corpus(db_session, FakeEmbedder(), titles=["14"])

    remaining = await db_session.scalar(
        text("SELECT count(*) FROM document WHERE source = 'title14'")
    )
    assert remaining == 1
