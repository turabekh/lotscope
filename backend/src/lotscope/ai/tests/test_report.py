from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.errors import GenerationError
from lotscope.ai.service import draft_parcel_report
from lotscope.zoning.seed import seed_zoning_standards

pytestmark = pytest.mark.integration


class _FakeGenerator:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured_user: str | None = None
        self.captured_system: str | None = None

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.captured_system = system
        self.captured_user = user
        return self._payload


_VALID = {
    "headline": "A buildable vacant RSA-5 lot with upside.",
    "sections": [
        {"heading": "Overview", "body": "Vacant RSA-5 lot."},
        {"heading": "Buildability", "body": "Buildable by-right."},
    ],
    "recommendation": "Worth a closer look before pursuing.",
    "confidence": "medium",
    "is_informational": True,
}


async def test_report_grounds_in_computed_facts(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, address, base_zoning_code, is_vacant) "
            "VALUES ('000000001', '1 Main St', 'RSA-5', true)"
        )
    )
    await db_session.flush()

    generator = _FakeGenerator(_VALID)
    result = await draft_parcel_report(db_session, "000000001", generator=generator)

    assert result is not None
    assert result.headline == _VALID["headline"]
    assert [section.heading for section in result.sections] == ["Overview", "Buildability"]
    assert result.recommendation
    assert result.confidence == "medium"
    assert result.is_informational is True
    assert result.sources
    assert generator.captured_user is not None
    assert "FACTS:" in generator.captured_user
    assert "RSA-5" in generator.captured_user
    assert "1 Main St" in generator.captured_user


async def test_report_carries_zoning_citation(db_session: AsyncSession) -> None:
    await seed_zoning_standards(db_session)
    await db_session.execute(
        text(
            "INSERT INTO parcel "
            "(parcel_number, address, base_zoning_code, lot_area_sqft, is_vacant) "
            "VALUES ('000000002', '2 Oak St', 'RSA-5', 1500, true)"
        )
    )
    await db_session.flush()

    generator = _FakeGenerator(_VALID)
    await draft_parcel_report(db_session, "000000002", generator=generator)

    assert generator.captured_user is not None
    assert "Title 14" in generator.captured_user


async def test_report_missing_parcel_returns_none(db_session: AsyncSession) -> None:
    generator = _FakeGenerator(_VALID)
    assert await draft_parcel_report(db_session, "999999999", generator=generator) is None


async def test_report_rejects_invalid_model_output(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000001')"))
    await db_session.flush()

    generator = _FakeGenerator({"confidence": "medium"})  # missing headline/sections/recommendation
    with pytest.raises(GenerationError):
        await draft_parcel_report(db_session, "000000001", generator=generator)
