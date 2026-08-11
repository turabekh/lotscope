from lotscope.ai.context import (
    MAX_CONTEXT_CHARS,
    ContextBudget,
    fit_to_budget,
)
from lotscope.ai.schemas import RetrievedDocument


def _document(identifier: int, *, section: str, chars: int) -> RetrievedDocument:
    return RetrievedDocument(
        id=identifier,
        source="phillycode",
        section=section,
        title=None,
        content="x" * chars,
        distance=0.1,
    )


def test_a_context_that_fits_is_passed_through_untouched() -> None:
    documents = [_document(1, section="14-701", chars=100)]

    assert fit_to_budget(documents, ContextBudget(max_chars=1000)) == documents


def test_the_budget_stops_at_the_document_that_would_overflow_it() -> None:
    documents = [
        _document(1, section="14-701", chars=400),
        _document(2, section="14-602", chars=400),
        _document(3, section="14-603", chars=400),
    ]

    kept = fit_to_budget(documents, ContextBudget(max_chars=900))

    assert [document.id for document in kept] == [1, 2]


def test_the_most_specific_reading_survives_a_tight_budget() -> None:
    documents = [
        _document(1, section="14-303(12)(e)", chars=500),
        _document(2, section="14-303", chars=500),
    ]

    kept = fit_to_budget(documents, ContextBudget(max_chars=600))

    assert [document.section for document in kept] == ["14-303(12)(e)"]


def test_a_single_document_larger_than_the_budget_is_still_sent() -> None:
    documents = [_document(1, section="14-701", chars=5000)]

    kept = fit_to_budget(documents, ContextBudget(max_chars=100))

    assert [document.id for document in kept] == [1]


def test_duplicates_are_removed_before_anything_is_measured() -> None:
    documents = [
        _document(1, section="14-701", chars=400),
        _document(1, section="14-701", chars=400),
        _document(2, section="14-602", chars=400),
    ]

    kept = fit_to_budget(documents, ContextBudget(max_chars=900))

    assert [document.id for document in kept] == [1, 2]


def test_an_empty_context_stays_empty() -> None:
    assert fit_to_budget([], ContextBudget(max_chars=100)) == []


def test_the_default_budget_is_large_enough_for_a_real_answer() -> None:
    assert MAX_CONTEXT_CHARS >= 16_000
