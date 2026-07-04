from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.errors import GenerationError
from lotscope.ai.service import summarize_parcel

pytestmark = pytest.mark.integration


class _FakeGenerator:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured_user: str | None = None

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.captured_user = user
        return self._payload


_VALID = {"summary": "A vacant RSA-5 lot.", "is_informational": True}


async def test_summarize_grounds_in_computed_facts(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, base_zoning_code, is_vacant) "
            "VALUES ('000000001', '1 Main St', 'RSA-5', true)"
        )
    )
    await db_session.flush()

    generator = _FakeGenerator(_VALID)
    result = await summarize_parcel(db_session, "000000001", generator=generator)

    assert result is not None
    assert result.summary == "A vacant RSA-5 lot."
    assert result.parcel_number == "000000001"
    assert result.verdict_version == "none"
    assert result.data_coverage == "low"
    assert result.is_informational is True
    assert result.sources
    # the prompt must carry the parcel's computed facts (grounding), not a free question
    assert generator.captured_user is not None
    assert "FACTS:" in generator.captured_user
    assert "RSA-5" in generator.captured_user
    assert "1 Main St" in generator.captured_user


async def test_summarize_missing_parcel_returns_none(db_session: AsyncSession) -> None:
    generator = _FakeGenerator(_VALID)
    assert await summarize_parcel(db_session, "999999999", generator=generator) is None


async def test_summarize_rejects_invalid_model_output(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000001')"))
    await db_session.flush()

    generator = _FakeGenerator({"confidence": "medium"})  # missing required 'summary'
    with pytest.raises(GenerationError):
        await summarize_parcel(db_session, "000000001", generator=generator)
