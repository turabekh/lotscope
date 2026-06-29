from typing import Any

import pytest
from pydantic import BaseModel

from lotscope.ai.errors import GenerationError
from lotscope.documents.extraction import build_extraction_prompt, extract_restrictions


class _FakeGenerator:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured_user: str | None = None

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.captured_user = user
        return self._payload


def test_build_extraction_prompt_truncates_and_includes_text() -> None:
    prompt = build_extraction_prompt("NO MULTI-FAMILY DWELLINGS")
    assert "DEED TEXT:" in prompt
    assert "NO MULTI-FAMILY DWELLINGS" in prompt


async def test_extract_restrictions_parses_validated_output() -> None:
    generator = _FakeGenerator(
        {
            "has_restrictions": True,
            "restrictions": [
                {
                    "kind": "use_restriction",
                    "text": "No multi-family dwellings permitted.",
                    "citation": "Paragraph 3",
                    "confidence": "high",
                }
            ],
        }
    )
    result = await extract_restrictions(generator, "...deed text...")
    assert result.has_restrictions is True
    assert result.restrictions[0].kind == "use_restriction"
    assert result.restrictions[0].confidence == "high"


async def test_extract_restrictions_rejects_invalid_output() -> None:
    generator = _FakeGenerator({"restrictions": [{"kind": "not_a_kind", "text": "x"}]})
    with pytest.raises(GenerationError):
        await extract_restrictions(generator, "text")
