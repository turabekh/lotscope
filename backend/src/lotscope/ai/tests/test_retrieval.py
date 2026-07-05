import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import (
    add_document,
    embed_and_search,
    fetch_district_documents,
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
        session, source="title14", section="A", content="alpha", embedding=_embedding(1.0, 0.0)
    )
    await add_document(
        session, source="title14", section="B", content="beta", embedding=_embedding(0.8, 0.6)
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
        source="title14",
        section="§ 14-701 (CMX-2)",
        content="cmx2",
        embedding=_embedding(0.1),
    )
    await add_document(
        session,
        source="title14",
        section="§ 14-701 (CMX-2.5)",
        content="cmx25",
        embedding=_embedding(0.2),
    )
    await add_document(
        session,
        source="title14",
        section="§ 14-701 (RSA-5)",
        content="rsa5",
        embedding=_embedding(0.3),
    )
    await session.flush()


async def test_fetch_district_documents_matches_exact_code(db_session: AsyncSession) -> None:
    await _seed_district_documents(db_session)

    cmx2 = await fetch_district_documents(db_session, "CMX2", source="title14")
    assert [doc.section for doc in cmx2] == ["§ 14-701 (CMX-2)"]


async def test_fetch_district_documents_is_hyphen_and_case_insensitive(
    db_session: AsyncSession,
) -> None:
    await _seed_district_documents(db_session)

    result = await fetch_district_documents(db_session, "cmx-2.5", source="title14")
    assert [doc.section for doc in result] == ["§ 14-701 (CMX-2.5)"]


async def test_fetch_district_documents_no_match_returns_empty(db_session: AsyncSession) -> None:
    await _seed_district_documents(db_session)

    assert await fetch_district_documents(db_session, "I-2", source="title14") == []


async def _seed_cross_market(session: AsyncSession) -> None:
    await add_document(
        session,
        source="title14",
        section="(RSA-5)",
        content="philadelphia rowhouse standards",
        embedding=_embedding(1.0, 0.0),
    )
    await add_document(
        session,
        source="zoning",
        section="(RF)",
        content="harrisburg residential standards",
        embedding=_embedding(1.0, 0.0),
        metadata={"market": "hbg"},
    )
    await add_document(
        session,
        source="zoning",
        section="(R1D)",
        content="pittsburgh residential standards",
        embedding=_embedding(1.0, 0.0),
        metadata={"market": "pgh"},
    )
    await session.flush()


async def test_market_filter_isolates_zoning_corpora(db_session: AsyncSession) -> None:
    await _seed_cross_market(db_session)

    phl = await vector_search(db_session, _embedding(1.0, 0.0), source="title14", market=None)
    assert {d.content for d in phl} == {"philadelphia rowhouse standards"}

    hbg = await vector_search(db_session, _embedding(1.0, 0.0), source="zoning", market="hbg")
    assert {d.content for d in hbg} == {"harrisburg residential standards"}

    # a Harrisburg query never surfaces Pittsburgh (shared source, different market)
    assert all("pittsburgh" not in d.content for d in hbg)


async def test_district_lookup_is_market_scoped(db_session: AsyncSession) -> None:
    await _seed_cross_market(db_session)

    hbg = await fetch_district_documents(db_session, "RF", source="zoning", market="hbg")
    assert {d.content for d in hbg} == {"harrisburg residential standards"}

    # the same district code under another market is not returned
    pgh_scope = await fetch_district_documents(db_session, "RF", source="zoning", market="pgh")
    assert pgh_scope == []
