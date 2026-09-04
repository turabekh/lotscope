import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import (
    add_document,
    embed_and_search,
    vector_search,
)

pytestmark = pytest.mark.integration


def _embedding(*leading: float) -> list[float]:
    values = list(leading)
    return values + [0.0] * (EMBEDDING_DIMENSIONS - len(values))


class _FakeEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector]


async def _seed_documents(session: AsyncSession) -> None:
    await add_document(
        session, source="phillycode", section="A", content="alpha", embedding=_embedding(1.0, 0.0)
    )
    await add_document(
        session, source="phillycode", section="B", content="beta", embedding=_embedding(0.8, 0.6)
    )
    await add_document(
        session, source="deeds", section="C", content="gamma", embedding=_embedding(0.0, 1.0)
    )
    await session.flush()


async def test_vector_search_orders_by_similarity(db_session: AsyncSession) -> None:
    await _seed_documents(db_session)

    results = await vector_search(db_session, _embedding(1.0, 0.0), limit=3)
    assert [doc.section for doc in results] == ["A", "B", "C"]
    assert results[0].distance <= results[1].distance


async def test_vector_search_filters_by_source(db_session: AsyncSession) -> None:
    await _seed_documents(db_session)

    results = await vector_search(db_session, _embedding(1.0, 0.0), limit=5, source="deeds")
    assert {doc.section for doc in results} == {"C"}


async def test_embed_and_search_uses_embedder(db_session: AsyncSession) -> None:
    await _seed_documents(db_session)

    results = await embed_and_search(
        db_session, _FakeEmbedder(_embedding(0.0, 1.0)), "anything", limit=1
    )
    assert results[0].section == "C"


async def _seed_district_documents(session: AsyncSession) -> None:
    await add_document(
        session,
        source="phillycode",
        section="§ 14-701 (CMX-2)",
        content="cmx2",
        embedding=_embedding(0.1),
    )
    await add_document(
        session,
        source="phillycode",
        section="§ 14-701 (CMX-2.5)",
        content="cmx25",
        embedding=_embedding(0.2),
    )
    await add_document(
        session,
        source="phillycode",
        section="§ 14-701 (RSA-5)",
        content="rsa5",
        embedding=_embedding(0.3),
    )
    await session.flush()
