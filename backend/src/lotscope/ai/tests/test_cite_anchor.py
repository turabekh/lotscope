import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.query_terms import extract_cites
from lotscope.ai.retrieval import add_document, fetch_documents_by_cite

pytestmark = pytest.mark.integration


def _vector(seed: float) -> list[float]:
    return [seed] * EMBEDDING_DIMENSIONS


async def _seed(session: AsyncSession) -> None:
    rows = [
        ("phillycode", "14-303(12)(e)", "14"),
        ("phillycode", "14-701", "14"),
        ("phillycode", "9-3010", "9"),
        ("phillycode", "§ 14-701 / § 14-602 (RSA-5)", None),
    ]
    for source, section, title_number in rows:
        metadata: dict[str, object] = {"provision_id": section}
        if title_number is not None:
            metadata["title_number"] = title_number
        await add_document(
            session,
            source=source,
            content=f"body of {section}",
            embedding=_vector(0.01),
            section=section,
            metadata=metadata,
        )
    await session.commit()


async def test_a_cite_in_the_question_reaches_its_provision_exactly(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    cites = extract_cites("what does 14-303(12)(e) require?")

    found = await fetch_documents_by_cite(db_session, cites, source="phillycode")

    assert [document.section for document in found] == ["14-303(12)(e)"]
    assert found[0].distance == 0.0


async def test_cites_come_back_in_the_order_they_were_asked_for(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await fetch_documents_by_cite(
        db_session, ["14-701", "14-303(12)(e)"], source="phillycode"
    )

    assert [document.section for document in found] == ["14-701", "14-303(12)(e)"]


async def test_a_title_scope_still_applies_to_an_exact_cite(db_session: AsyncSession) -> None:
    await _seed(db_session)

    found = await fetch_documents_by_cite(
        db_session, ["9-3010"], source="phillycode", titles=["14"]
    )

    assert found == []


async def test_an_unknown_cite_returns_nothing_rather_than_guessing(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)

    found = await fetch_documents_by_cite(db_session, ["14-999"], source="phillycode")

    assert found == []


async def test_no_cites_costs_no_query(db_session: AsyncSession) -> None:
    await _seed(db_session)

    assert await fetch_documents_by_cite(db_session, [], source="phillycode") == []
