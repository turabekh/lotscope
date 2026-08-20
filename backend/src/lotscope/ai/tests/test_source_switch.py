import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.retrieval import add_document
from lotscope.ai.schemas import ParcelAnswer
from lotscope.ai.service import ask_the_parcel
from lotscope.api.parcels import _ask_cache_key

_MODEL = "claude-sonnet-4-6"

pytestmark = pytest.mark.integration


class RecordingGenerator:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, *, system: str, user: str, schema: type) -> dict[str, object]:
        self.prompts.append(user)
        return {
            "answer": "It depends on the district standard.",
            "citations": [{"source": "Title 14", "section": "14-701"}],
            "confidence": "medium",
            "is_informational": True,
        }


class FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.01] * EMBEDDING_DIMENSIONS for _ in texts]


_PARCEL = text(
    "INSERT INTO parcel (market_code, parcel_number, address, base_zoning_code, "
    "resolved_zoning_code, source, last_synced_at) VALUES ('phl', 'phl:555000001', "
    "'1 SWITCH ST', 'RSA-5', 'RSA-5', 'test', now())"
)
_PROVISION = text(
    "INSERT INTO code_provision (market_code, id, cite, doc, kind, title_number, parent, "
    "ordinal, path, heading, text, raw_text, refs, note_refs, table_data, page_start, "
    "page_end, source_file, source_version) VALUES ('phl', :id, :id, 'code', 'section', "
    "'14', null, :ordinal, (:path)::jsonb, null, 'body text', 'body text', '[]'::jsonb, "
    "'[]'::jsonb, null, 1, 1, 'x.pdf', 'May 25, 2026')"
)
_STANDARD = text(
    "INSERT INTO zoning_standard (market_code, code, code_version, permitted_uses, dimensional) "
    "VALUES ('phl', 'RSA-5', 'title14-quickguide-2026-02', '[]'::jsonb, '{}'::jsonb)"
)


async def _seed(session: AsyncSession) -> None:
    await session.execute(_PARCEL)
    await session.execute(_STANDARD)
    await add_document(
        session,
        source="title14",
        content="incumbent quick guide body",
        embedding=[0.01] * EMBEDDING_DIMENSIONS,
        section="§ 14-701 / § 14-602 (RSA-5)",
        metadata={},
    )
    for ordinal, cite in enumerate(["14-701", "14-602"], start=1):
        await session.execute(
            _PROVISION,
            {"id": cite, "ordinal": ordinal, "path": json.dumps(["14", cite])},
        )
        await add_document(
            session,
            source="phillycode",
            content=f"canonical body of {cite}",
            embedding=[0.01] * EMBEDDING_DIMENSIONS,
            section=cite,
            metadata={"provision_id": cite, "title_number": "14"},
        )
    await session.commit()


async def _ask(session: AsyncSession, generator: RecordingGenerator, override: str | None) -> None:
    answer = await ask_the_parcel(
        session,
        "phl:555000001",
        "what is the minimum lot area?",
        embedder=FakeEmbedder(),
        generator=generator,
        source_override=override,
    )
    assert isinstance(answer, ParcelAnswer)


async def test_the_default_still_answers_from_the_quick_guide(db_session: AsyncSession) -> None:
    await _seed(db_session)
    generator = RecordingGenerator()

    await _ask(db_session, generator, None)

    assert "incumbent quick guide body" in generator.prompts[0]
    assert "canonical body of" not in generator.prompts[0]


async def test_the_configured_default_of_title14_changes_nothing(db_session: AsyncSession) -> None:
    await _seed(db_session)
    unset = RecordingGenerator()
    configured = RecordingGenerator()

    await _ask(db_session, unset, None)
    await _ask(db_session, configured, "title14")

    assert configured.prompts[0] == unset.prompts[0]


async def test_the_override_reaches_the_canonical_corpus(db_session: AsyncSession) -> None:
    await _seed(db_session)
    generator = RecordingGenerator()

    await _ask(db_session, generator, "phillycode")

    assert "canonical body of 14-701" in generator.prompts[0]
    assert "incumbent quick guide body" not in generator.prompts[0]


async def test_the_parcels_own_district_anchors_the_canonical_context(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    generator = RecordingGenerator()

    await _ask(db_session, generator, "phillycode")

    assert "canonical body of 14-602" in generator.prompts[0]


def test_the_two_arms_cannot_read_each_others_cached_answers() -> None:
    incumbent = _ask_cache_key("phl:1", "how tall?", "title14", _MODEL)
    canonical = _ask_cache_key("phl:1", "how tall?", "phillycode", _MODEL)

    assert incumbent != canonical


def test_the_incumbent_cache_key_still_identifies_the_same_question() -> None:
    first = _ask_cache_key("phl:1", "How  TALL?", "title14", _MODEL)
    second = _ask_cache_key("phl:1", "how tall?", "title14", _MODEL)

    assert first == second


def test_every_ai_cache_key_carries_its_prompt_version_and_model() -> None:
    from lotscope.ai.prompts import PROMPT_VERSION, REPORT_PROMPT_VERSION, SUMMARY_PROMPT_VERSION
    from lotscope.api.parcels import _generation_scope

    summary = _generation_scope(SUMMARY_PROMPT_VERSION, "model-a")
    report = _generation_scope(REPORT_PROMPT_VERSION, "model-a")
    ask = _generation_scope(PROMPT_VERSION, "model-a")

    assert summary != report != ask
    for scope, version in (
        (summary, SUMMARY_PROMPT_VERSION),
        (report, REPORT_PROMPT_VERSION),
        (ask, PROMPT_VERSION),
    ):
        assert version in scope
        assert "model-a" in scope


def test_a_model_swap_invalidates_a_cached_answer() -> None:
    from lotscope.api.parcels import _ask_cache_key

    incumbent = _ask_cache_key("phl:1", "how tall?", "title14", "claude-sonnet-4-6")
    swapped = _ask_cache_key("phl:1", "how tall?", "title14", "claude-opus-5")

    assert incumbent != swapped


def test_a_prompt_bump_invalidates_a_cached_summary() -> None:
    from lotscope.api.parcels import _generation_scope

    before = _generation_scope("parcel-summary-v2", "model-a")
    after = _generation_scope("parcel-summary-v3", "model-a")

    assert before != after
