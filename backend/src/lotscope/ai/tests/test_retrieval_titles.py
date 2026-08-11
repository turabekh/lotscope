import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import add_document, vector_search

pytestmark = pytest.mark.integration


def _vector(seed: float) -> list[float]:
    return [seed] * EMBEDDING_DIMENSIONS


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("phillycode", "14-701", "14", 0.01),
        ("phillycode", "14-602", "14", 0.011),
        ("phillycode", "9-3010", "9", 0.012),
        ("phillycode", "19-1301", "19", 0.013),
        ("title14", "§ 14-701 (RSA-5)", None, 0.014),
    ]
    for source, section, title_number, seed in rows:
        metadata: dict[str, object] = {"provision_id": section}
        if title_number is not None:
            metadata["title_number"] = title_number
        await add_document(
            session,
            source=source,
            content=f"content for {section}",
            embedding=_vector(seed),
            section=section,
            metadata=metadata,
        )
    await session.commit()


async def test_an_unscoped_search_still_sees_every_title(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await vector_search(db_session, _vector(0.01), limit=10, source="phillycode")

    assert {document.section for document in found} == {"14-701", "14-602", "9-3010", "19-1301"}


async def test_a_title_scope_excludes_everything_outside_it(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await vector_search(
        db_session, _vector(0.01), limit=10, source="phillycode", titles=["14"]
    )

    assert {document.section for document in found} == {"14-701", "14-602"}


async def test_several_titles_can_be_in_scope_at_once(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await vector_search(
        db_session, _vector(0.01), limit=10, source="phillycode", titles=["14", "9"]
    )

    assert {document.section for document in found} == {"14-701", "14-602", "9-3010"}


async def test_an_empty_title_list_is_treated_as_no_scope_at_all(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await vector_search(db_session, _vector(0.01), limit=10, source="phillycode", titles=[])

    assert len(found) == 4


async def test_the_incumbent_source_is_unaffected_by_title_scoping(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    found = await vector_search(db_session, _vector(0.014), limit=10, source="title14")

    assert [document.section for document in found] == ["§ 14-701 (RSA-5)"]


async def test_rows_without_a_title_number_are_excluded_by_a_title_scope(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    await db_session.execute(
        text(
            "INSERT INTO document (source, section, content, doc_metadata, embedding) "
            "VALUES ('phillycode', 'no-title', 'x', (:metadata)::jsonb, (:embedding)::vector)"
        ),
        {
            "metadata": json.dumps({"provision_id": "no-title"}),
            "embedding": "[" + ",".join(["0.01"] * EMBEDDING_DIMENSIONS) + "]",
        },
    )
    await db_session.commit()

    found = await vector_search(
        db_session, _vector(0.01), limit=10, source="phillycode", titles=["14"]
    )

    assert "no-title" not in {document.section for document in found}
