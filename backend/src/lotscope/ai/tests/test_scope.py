from lotscope.ai.scope import (
    PHILLYCODE_SOURCE,
    TITLE_14_SOURCE,
    RetrievalScope,
    zoning_retrieval_scope,
)


def test_philadelphia_still_reads_the_quick_guide_when_nothing_is_overridden() -> None:
    scope = zoning_retrieval_scope("phl")

    assert scope == RetrievalScope(source=TITLE_14_SOURCE, market=None, titles=None)


def test_the_override_reaches_the_canonical_corpus_scoped_to_title_14() -> None:
    scope = zoning_retrieval_scope("phl", source_override=PHILLYCODE_SOURCE)

    assert scope == RetrievalScope(source=PHILLYCODE_SOURCE, market=None, titles=["14"])


def test_an_explicit_title_scope_narrows_the_canonical_corpus() -> None:
    scope = zoning_retrieval_scope("phl", source_override=PHILLYCODE_SOURCE, titles=["9", "14"])

    assert scope.titles == ["9", "14"]


def test_a_title_scope_without_the_override_changes_nothing() -> None:
    scope = zoning_retrieval_scope("phl", titles=["9"])

    assert scope == RetrievalScope(source=TITLE_14_SOURCE, market=None, titles=None)
