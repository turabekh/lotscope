import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.context import expand_to_windows, section_window_cites
from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import add_document
from lotscope.ai.schemas import RetrievedDocument
from lotscope.ai.scope import RetrievalScope

pytestmark = pytest.mark.integration

_PROVISION = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES ('phl', :id, :id, 'code', :kind, "
    "'14', :parent, :ordinal, (:path)::jsonb, null, 'body', 'body', '[]'::jsonb, "
    "'[]'::jsonb, null, 1, 1, 'x.pdf', 'May 25, 2026')"
)

TREE = [
    ("14-500", "section", None, 1),
    ("14-500(1)", "subsection", "14-500", 2),
    ("14-500(2)", "subsection", "14-500", 3),
    ("14-500(3)", "subsection", "14-500", 4),
    ("14-900", "section", None, 5),
    ("14-900(1)", "subsection", "14-900", 6),
]


async def _seed(session: AsyncSession) -> None:
    for provision_id, kind, parent, ordinal in TREE:
        await session.execute(
            _PROVISION,
            {
                "id": provision_id,
                "kind": kind,
                "parent": parent,
                "ordinal": ordinal,
                "path": json.dumps(["14", provision_id]),
            },
        )
        await add_document(
            session,
            source="phillycode",
            content=f"body of {provision_id}",
            embedding=[0.01] * EMBEDDING_DIMENSIONS,
            section=provision_id,
            metadata={"provision_id": provision_id, "title_number": "14"},
        )
    await session.commit()


def _hit(section: str) -> RetrievedDocument:
    return RetrievedDocument(
        id=0, source="phillycode", section=section, title=None, content="", distance=0.2
    )


async def test_a_leaf_hit_pulls_in_the_section_that_contains_it(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await section_window_cites(db_session, "14-500(2)", market_code="phl")

    assert cites[0] == "14-500"


async def test_the_window_carries_the_siblings_that_give_it_meaning(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await section_window_cites(db_session, "14-500(2)", market_code="phl")

    assert "14-500(1)" in cites
    assert "14-500(3)" in cites


async def test_a_window_is_capped_so_one_big_section_cannot_take_over(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await section_window_cites(db_session, "14-500(2)", market_code="phl", max_provisions=2)

    assert len(cites) == 2


async def test_two_hits_in_the_same_section_produce_one_window_not_two(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    documents = await expand_to_windows(
        db_session,
        [_hit("14-500(1)"), _hit("14-500(2)")],
        market_code="phl",
        scope=RetrievalScope(source="phillycode", market=None, titles=["14"]),
    )

    sections = [document.section for document in documents]
    assert len(sections) == len(set(sections))


async def test_hits_beyond_the_window_cap_are_left_out(db_session: AsyncSession) -> None:
    await _seed(db_session)

    documents = await expand_to_windows(
        db_session,
        [_hit("14-500(1)"), _hit("14-900(1)")],
        market_code="phl",
        scope=RetrievalScope(source="phillycode", market=None, titles=["14"]),
        max_windows=1,
    )

    assert all(document.section is not None for document in documents)
    assert not any(str(document.section).startswith("14-900") for document in documents)


async def test_a_hit_with_no_resolvable_section_expands_to_nothing(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    documents = await expand_to_windows(
        db_session,
        [_hit("14-does-not-exist")],
        market_code="phl",
        scope=RetrievalScope(source="phillycode", market=None, titles=["14"]),
    )

    assert documents == []


async def test_a_window_reaches_the_tables_that_hold_the_answer(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await db_session.execute(
        _PROVISION,
        {
            "id": "14-500(2)(a)#table1",
            "kind": "table",
            "parent": "14-500(2)",
            "ordinal": 20,
            "path": json.dumps(["14", "14-500", "14-500(2)", "14-500(2)(a)#table1"]),
        },
    )
    await db_session.commit()

    cites = await section_window_cites(db_session, "14-500(2)", market_code="phl")

    assert "14-500(2)(a)#table1" in cites


async def test_a_section_hit_expands_from_itself_not_its_parent(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    cites = await section_window_cites(db_session, "14-500", market_code="phl")

    assert cites[0] == "14-500"
    assert "14-500(1)" in cites
