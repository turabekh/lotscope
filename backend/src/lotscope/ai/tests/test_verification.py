import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.phillycode import derive_corpus
from lotscope.ai.verification import verify_derivation

pytestmark = pytest.mark.integration


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * EMBEDDING_DIMENSIONS for _ in texts]


_INSERT = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES (:market_code, :id, :cite, 'code', :kind, "
    ":title_number, :parent, :ordinal, (:path)::jsonb, :heading, :text, :text, '[]'::jsonb, "
    "'[]'::jsonb, null, 1, 1, 'x.pdf', 'May 25, 2026')"
)

LONG = (
    "A provision long enough that it stands as its own document rather than folding into "
    "a parent, which needs more than one hundred and twenty characters of body text."
)


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("14", "14", "title", None, 1, ["14"], "Title 14", ""),
        ("14-800", "14-800", "chapter", "14", 2, ["14", "14-800"], "PARKING", LONG),
        ("14-802", "14-802", "section", "14-800", 3, ["14", "14-800", "14-802"], "Ratios", LONG),
    ]
    for provision_id, cite, kind, parent, ordinal, path, heading, body in rows:
        await session.execute(
            _INSERT,
            {
                "market_code": "phl",
                "id": provision_id,
                "cite": cite,
                "kind": kind,
                "title_number": "14",
                "parent": parent,
                "ordinal": ordinal,
                "path": json.dumps(path),
                "heading": heading,
                "text": body,
            },
        )
    await session.commit()


async def test_a_fully_derived_title_reconciles_and_passes(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await derive_corpus(db_session, FakeEmbedder(), titles=["14"])
    await db_session.commit()

    report = await verify_derivation(
        db_session, market_code="phl", derivation_version="d2", require_complete=True
    )

    assert [title.shortfall for title in report.titles] == [0]
    assert report.titles[0].ledger_status == "succeeded"
    assert report.ok


async def test_a_missing_document_fails_a_title_the_ledger_claims_complete(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await derive_corpus(db_session, FakeEmbedder(), titles=["14"])
    await db_session.commit()
    await db_session.execute(
        text("DELETE FROM document WHERE source='phillycode' AND section='14-802'")
    )
    await db_session.commit()

    report = await verify_derivation(
        db_session, market_code="phl", derivation_version="d2", require_complete=False
    )

    assert report.titles[0].shortfall == 1
    assert report.titles[0].claimed_complete
    assert [title.title_number for title in report.breached] == ["14"]
    assert not report.ok


async def test_an_undelivered_title_is_silent_until_completeness_is_demanded(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    lenient = await verify_derivation(
        db_session, market_code="phl", derivation_version="d2", require_complete=False
    )
    strict = await verify_derivation(
        db_session, market_code="phl", derivation_version="d2", require_complete=True
    )

    assert lenient.titles[0].actual == 0
    assert lenient.titles[0].ledger_status is None
    assert lenient.ok
    assert not strict.ok


async def test_a_stale_derivation_version_fails_even_when_counts_agree(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await derive_corpus(db_session, FakeEmbedder(), titles=["14"])
    await db_session.commit()
    await db_session.execute(
        text(
            "UPDATE document SET doc_metadata = jsonb_set(doc_metadata, "
            "'{derivation_version}', '\"d1\"') WHERE source='phillycode'"
        )
    )
    await db_session.commit()

    report = await verify_derivation(
        db_session, market_code="phl", derivation_version="d2", require_complete=False
    )

    assert report.titles[0].shortfall == 0
    assert [title.title_number for title in report.stale_versions] == ["14"]
    assert not report.ok


async def test_the_ledger_records_a_row_for_every_title_derived(db_session: AsyncSession) -> None:
    await _seed(db_session)
    await derive_corpus(db_session, FakeEmbedder(), titles=["14"])
    await db_session.commit()

    rows = (
        await db_session.execute(
            text(
                "SELECT title_number, status, documents, provisions_seen, reconciled, "
                "derivation_version FROM derivation_run WHERE source='phillycode'"
            )
        )
    ).all()

    assert len(rows) == 1
    assert rows[0].title_number == "14"
    assert rows[0].status == "succeeded"
    assert rows[0].documents == 2
    assert rows[0].provisions_seen == 3
    assert rows[0].reconciled
    assert rows[0].derivation_version == "d2"
