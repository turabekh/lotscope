import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.corpus.service import MINIMUM_COVERAGE_PCT, corpus_health

pytestmark = pytest.mark.integration

_PROVISION = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES ('phl', :id, :id, 'code', 'section', "
    ":title_number, null, :ordinal, '[]'::jsonb, null, 'body', '', '[]'::jsonb, '[]'::jsonb, "
    "null, 1, 1, 'x.pdf', 'May 25, 2026')"
)
_DOCUMENT = text(
    "INSERT INTO document (source, section, content, doc_metadata, embedding) VALUES "
    "('phillycode', :id, 'body', (:metadata)::jsonb, "
    "CASE WHEN :embedded THEN (:vector)::vector ELSE NULL END)"
)


async def _seed(session: AsyncSession, *, embedded: bool = True, folded: bool = False) -> None:
    import json

    for ordinal, provision_id in enumerate(["14-1", "14-2"], start=1):
        await session.execute(
            _PROVISION, {"id": provision_id, "title_number": "14", "ordinal": ordinal}
        )
    metadata = {
        "provision_id": "14-1",
        "title_number": "14",
        "folded_provision_ids": ["14-2"] if folded else [],
    }
    await session.execute(
        _DOCUMENT,
        {
            "id": "14-1",
            "metadata": json.dumps(metadata),
            "embedded": embedded,
            "vector": "[" + ",".join(["0.01"] * EMBEDDING_DIMENSIONS) + "]",
        },
    )
    await session.flush()


async def test_coverage_measures_embedded_documents_not_provisions(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    health = await corpus_health(db_session)

    assert health.total_provisions == 2
    assert health.total_documents == 1
    assert health.coverage_pct == 100.0, (
        "coverage is about documents that should have a vector; provisions the derivation "
        "deliberately skips are not missing coverage"
    )


async def test_a_document_without_a_vector_drags_coverage_below_the_floor(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session, embedded=False)
    health = await corpus_health(db_session)

    assert health.coverage_pct == 0.0
    assert health.coverage_pct < MINIMUM_COVERAGE_PCT
    assert health.healthy is False


async def test_a_folded_provision_counts_as_represented(db_session: AsyncSession) -> None:
    await _seed(db_session, folded=True)
    health = await corpus_health(db_session)

    assert health.total_represented == 2, "a provision folded into a parent document is covered"
    assert health.represented_pct == 100.0


async def test_a_corpus_below_the_provision_floor_is_unhealthy(db_session: AsyncSession) -> None:
    await _seed(db_session)
    health = await corpus_health(db_session)

    assert health.total_provisions == 2
    assert health.healthy is False, "two provisions cannot pass a 25,000 floor"


async def test_the_endpoint_reports_503_when_the_corpus_is_short(
    db_session: AsyncSession,
) -> None:
    from httpx import ASGITransport, AsyncClient

    from lotscope.api.app import create_app
    from lotscope.api.deps import get_session

    await _seed(db_session)
    app = create_app()

    async def _override() -> object:
        yield db_session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/corpus")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["source"] == "phillycode"
    assert body["minimum_provisions"] == 25_000
    assert body["computed_at"]
