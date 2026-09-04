import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.context import expand_refs
from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.prompts import build_user_prompt
from lotscope.ai.retrieval import add_document
from lotscope.ai.schemas import RetrievedDocument
from lotscope.ai.scope import RetrievalScope

pytestmark = pytest.mark.integration

_PROVISION = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES ('phl', :id, :id, 'code', 'subsection', "
    ":title_number, null, :ordinal, (:path)::jsonb, null, 'body', 'body', (:refs)::jsonb, "
    "'[]'::jsonb, null, 1, 1, 'x.pdf', 'May 25, 2026')"
)

PHL = RetrievalScope(source="phillycode", market=None, titles=["14"])


async def _seed(session: AsyncSession, *, refs: list[str]) -> None:
    rows = [
        ("14-303(12)(e)", "14", refs),
        ("14-701", "14", []),
        ("14-602", "14", []),
        ("14-800", "14", []),
        ("14-900", "14", []),
        ("9-3010", "9", []),
    ]
    for provision_id, title_number, provision_refs in rows:
        await session.execute(
            _PROVISION,
            {
                "id": provision_id,
                "title_number": title_number,
                "ordinal": len(provision_id),
                "path": json.dumps([title_number, provision_id]),
                "refs": json.dumps(provision_refs),
            },
        )
        await add_document(
            session,
            source="phillycode",
            content=f"body of {provision_id}",
            embedding=[0.01] * EMBEDDING_DIMENSIONS,
            section=provision_id,
            metadata={"provision_id": provision_id, "title_number": title_number},
        )
    await session.commit()


def _hit(section: str) -> RetrievedDocument:
    return RetrievedDocument(
        id=0, source="phillycode", section=section, title=None, content="", distance=0.2
    )


async def test_a_provision_that_cites_another_brings_it_along(db_session: AsyncSession) -> None:
    await _seed(db_session, refs=["14-701"])

    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    assert [document.section for document in found] == ["14-701"]


async def test_the_cap_holds_when_a_provision_cites_the_world(db_session: AsyncSession) -> None:
    await _seed(db_session, refs=["14-701", "14-602", "14-800", "14-900"])

    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    assert len(found) == 3


async def test_each_reference_says_which_provision_reached_it(db_session: AsyncSession) -> None:
    await _seed(db_session, refs=["14-701"])

    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    assert found[0].via == "14-303(12)(e)"


async def test_the_attribution_is_visible_to_the_model(db_session: AsyncSession) -> None:
    await _seed(db_session, refs=["14-701"])
    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    prompt = build_user_prompt("q", "facts", found)

    assert "referenced by 14-303(12)(e)" in prompt


async def test_a_document_nobody_referenced_reads_exactly_as_before() -> None:
    plain = RetrievedDocument(
        id=1, source="phillycode", section="§ 14-701", title=None, content="body", distance=0.1
    )

    prompt = build_user_prompt("q", "facts", [plain])

    assert "[phillycode § 14-701] body" in prompt
    assert "referenced by" not in prompt


async def test_a_reference_outside_the_title_scope_is_not_pulled_in(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session, refs=["9-3010"])

    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    assert found == []


async def test_a_provision_with_no_references_expands_to_nothing(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session, refs=[])

    found = await expand_refs(db_session, [_hit("14-303(12)(e)")], market_code="phl", scope=PHL)

    assert found == []
