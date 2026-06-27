from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.errors import UngroundedAnswerError
from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import add_document
from lotscope.ai.service import ask_the_parcel

pytestmark = pytest.mark.integration


def _embedding(*leading: float) -> list[float]:
    values = list(leading)
    return values + [0.0] * (EMBEDDING_DIMENSIONS - len(values))


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embedding(1.0, 0.0)]


class _FakeGenerator:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured_user: str | None = None

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.captured_user = user
        return self._payload


async def test_ask_the_parcel_grounds_and_cites(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('000000001', 'RSA-5')")
    )
    await add_document(
        db_session,
        source="title14",
        section="14-701",
        content="RSA-5 minimum lot area is 1,440 sqft.",
        embedding=_embedding(1.0, 0.0),
    )
    await db_session.flush()

    generator = _FakeGenerator(
        {
            "answer": "Yes, a single-family home is permitted by-right.",
            "citations": [{"source": "Title 14", "section": "14-701"}],
            "confidence": "high",
        }
    )
    answer = await ask_the_parcel(
        db_session,
        "000000001",
        "Can I build a house?",
        embedder=_FakeEmbedder(),
        generator=generator,
    )

    assert answer is not None
    assert answer.citations[0].section == "14-701"
    assert answer.is_informational is True
    assert generator.captured_user is not None
    assert "RSA-5 minimum lot area" in generator.captured_user


async def test_ask_the_parcel_pins_parcel_district_over_nearer_neighbor(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('000000002', 'CMX-2')")
    )
    await add_document(
        db_session,
        source="title14",
        section="§ 14-701 (CMX-2.5)",
        content="CMX-2.5 max height 55 ft",
        embedding=_embedding(1.0, 0.0),
    )
    await add_document(
        db_session,
        source="title14",
        section="§ 14-701 (CMX-2)",
        content="CMX-2 max height 38 ft",
        embedding=_embedding(0.0, 1.0),
    )
    await db_session.flush()

    generator = _FakeGenerator(
        {
            "answer": "Up to 38 ft.",
            "citations": [{"source": "Title 14", "section": "§ 14-701 (CMX-2)"}],
            "confidence": "medium",
        }
    )
    answer = await ask_the_parcel(
        db_session,
        "000000002",
        "How tall can I build?",
        embedder=_FakeEmbedder(),
        generator=generator,
    )

    assert answer is not None
    prompt = generator.captured_user
    assert prompt is not None
    assert prompt.index("CMX-2 max height 38 ft") < prompt.index("CMX-2.5 max height 55 ft")


async def test_ask_the_parcel_rejects_uncited_answer(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000001')"))
    await db_session.flush()

    generator = _FakeGenerator({"answer": "Maybe.", "citations": [], "confidence": "low"})
    with pytest.raises(UngroundedAnswerError):
        await ask_the_parcel(
            db_session,
            "000000001",
            "Question?",
            embedder=_FakeEmbedder(),
            generator=generator,
        )


async def test_ask_the_parcel_returns_none_when_missing(db_session: AsyncSession) -> None:
    result = await ask_the_parcel(
        db_session,
        "999999999",
        "Question?",
        embedder=_FakeEmbedder(),
        generator=_FakeGenerator({}),
    )
    assert result is None
