import pytest

from lotscope.api.parcels import _ask_cache_key
from lotscope.goldset.ask_harness import PromptCapturingGenerator, score_run
from lotscope.goldset.ask_metrics import (
    CaseScore,
    citation_precision,
    context_sections,
    divergences,
    percentile,
    primary_hit,
    refusal_correct,
    summarize,
)
from lotscope.goldset.ask_schemas import AskCase

PROMPT = (
    "QUESTION:\nwhat is the minimum lot area?\n\n"
    "CONTEXT - PARCEL FACTS:\nParcel phl:1\n\n"
    "CONTEXT - SOURCE DOCUMENTS:\n"
    "[phillycode 14-701] section body\n"
    "[phillycode 14-701(2)(b)[11]#table1] Table 14-701-1 body\n"
    "[phillycode 14-514(5)(a) · referenced by 14-701] overlay body\n"
)


def _case(**overrides: object) -> AskCase:
    base: dict[str, object] = {
        "question_id": "q1",
        "question": "what is the minimum lot area?",
        "parcel_number": "phl:1",
        "category": "district_dimensional",
        "coverage": "shared",
        "primary_cites": ["14-701(2)(b)[11]#table1"],
        "acceptable_cites": ["14-701"],
    }
    base.update(overrides)
    return AskCase.model_validate(base)


def test_the_context_is_read_from_the_prompt_the_model_actually_saw() -> None:
    assert context_sections(PROMPT) == [
        "14-701",
        "14-701(2)(b)[11]#table1",
        "14-514(5)(a)",
    ]


def test_a_referenced_document_keeps_its_own_identity_in_the_context() -> None:
    assert "14-514(5)(a)" in context_sections(PROMPT)


def test_a_prompt_with_no_documents_yields_no_context() -> None:
    assert context_sections("QUESTION:\nx\n") == []


def test_the_expected_provision_counts_as_hit_when_cited() -> None:
    citations = [{"source": "Title 14", "section": "14-701(2)(b)[11]#table1"}]

    assert primary_hit(_case(), citations)


def test_citing_only_the_parent_section_is_not_a_hit_on_the_table() -> None:
    citations = [{"source": "Title 14", "section": "14-999"}]

    assert not primary_hit(_case(), citations)


def test_precision_counts_acceptable_cites_as_relevant() -> None:
    citations = [
        {"source": "Title 14", "section": "14-701(2)(b)[11]#table1"},
        {"source": "Title 14", "section": "14-701"},
    ]

    assert citation_precision(_case(), citations) == 1.0


def test_precision_penalises_an_unrelated_citation() -> None:
    citations = [
        {"source": "Title 14", "section": "14-701(2)(b)[11]#table1"},
        {"source": "Title 14", "section": "19-1301"},
    ]

    assert citation_precision(_case(), citations) == 0.5


def test_an_answer_with_no_citations_has_no_precision_to_report() -> None:
    assert citation_precision(_case(), []) is None


def test_a_refusal_is_correct_only_when_it_also_cites_nothing() -> None:
    assert refusal_correct("That is not in the provided context.", [])
    assert not refusal_correct(
        "That is not in the provided context.",
        [{"source": "Title 14", "section": "14-701"}],
    )
    assert not refusal_correct("The minimum lot area is 960 sq ft.", [])


def test_retrieval_and_citation_are_scored_independently() -> None:
    from lotscope.goldset.ask_harness import ArmRun

    run = ArmRun(
        arm="phillycode",
        question_id="q1",
        answer="...",
        citations=[],
        context=context_sections(PROMPT),
        latency_seconds=1.0,
    )

    score = score_run(_case(), run)

    assert score.retrieval_present
    assert score.retrieval_position == 2
    assert not score.primary_hit


def test_a_retrieved_but_uncited_provision_is_named_as_such() -> None:
    scores = [
        CaseScore(
            question_id="q1",
            arm="phillycode",
            primary_hit=False,
            citation_precision=None,
            retrieval_present=True,
            retrieval_position=2,
            refusal_expected=False,
            refusal_correct=None,
            latency_seconds=1.0,
            context_documents=3,
        )
    ]

    assert divergences(scores)["retrieved_but_uncited"] == ["q1"]
    assert divergences(scores)["cited_without_retrieval"] == []


def test_the_scorecard_excludes_refusal_cases_from_the_hit_rate() -> None:
    scores = [
        CaseScore(
            question_id="a",
            arm="phillycode",
            primary_hit=True,
            citation_precision=1.0,
            retrieval_present=True,
            retrieval_position=1,
            refusal_expected=False,
            refusal_correct=None,
            latency_seconds=2.0,
            context_documents=5,
        ),
        CaseScore(
            question_id="b",
            arm="phillycode",
            primary_hit=False,
            citation_precision=None,
            retrieval_present=False,
            retrieval_position=None,
            refusal_expected=True,
            refusal_correct=True,
            latency_seconds=4.0,
            context_documents=0,
        ),
    ]

    card = summarize("phillycode", scores)

    assert card.primary_hit_rate == 1.0
    assert card.refusal_correct_rate == 1.0
    assert card.cases == 2


def test_percentiles_hold_on_a_single_value() -> None:
    assert percentile([3.0], 0.5) == 3.0
    assert percentile([], 0.95) == 0.0


def test_the_two_arms_cannot_share_a_cached_answer() -> None:
    assert _ask_cache_key("phl:1", "how tall?", "title14") != _ask_cache_key(
        "phl:1", "how tall?", "phillycode"
    )


def test_the_capturing_generator_passes_the_prompt_through_unchanged() -> None:
    class Inner:
        def __init__(self) -> None:
            self.seen = ""

        async def generate(self, *, system: str, user: str, schema: type) -> dict[str, object]:
            self.seen = user
            return {"ok": True}

    inner = Inner()
    capturing = PromptCapturingGenerator(inner)

    import asyncio

    result = asyncio.run(capturing.generate(system="s", user=PROMPT, schema=dict))

    assert inner.seen == PROMPT
    assert capturing.last_prompt == PROMPT
    assert result == {"ok": True}


@pytest.mark.parametrize("marker", ["not in the provided context", "unable to"])
def test_refusal_markers_are_recognised(marker: str) -> None:
    assert refusal_correct(f"Sorry, {marker} for that question.", [])


def test_citing_the_parent_section_does_not_score_as_the_table_it_contains() -> None:
    citations = [{"source": "Title 14", "section": "14-701"}]

    assert not primary_hit(_case(), citations)


def test_a_citation_carrying_the_cite_plus_its_caption_still_counts() -> None:
    citations = [{"source": "phillycode", "section": "14-701(2)(b)[11]#table1 — Table 14-701-1"}]

    assert primary_hit(_case(), citations)
