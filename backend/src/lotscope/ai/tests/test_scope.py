from lotscope.ai.scope import PHILLYCODE_SOURCE, RetrievalScope, zoning_retrieval_scope


def test_zoning_answers_read_the_canonical_corpus_scoped_to_title_14() -> None:
    assert zoning_retrieval_scope() == RetrievalScope(
        source=PHILLYCODE_SOURCE, market=None, titles=["14"]
    )


def test_an_explicit_title_scope_widens_beyond_title_14() -> None:
    assert zoning_retrieval_scope(["9", "14"]).titles == ["9", "14"]


def test_the_scope_is_never_market_filtered() -> None:
    assert zoning_retrieval_scope().market is None
