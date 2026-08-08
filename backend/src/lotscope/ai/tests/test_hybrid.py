from lotscope.ai.hybrid import Candidate, merge_candidates


def _c(pid: str, origin: str) -> Candidate:
    return Candidate(provision_id=pid, cite=pid, origin=origin)


def test_lexical_candidates_come_before_vector_ones() -> None:
    merged = merge_candidates([_c("a", "lexical")], [_c("b", "vector")], limit=10)

    assert [c.provision_id for c in merged] == ["a", "b"]
    assert [c.origin for c in merged] == ["lexical", "vector"]


def test_a_provision_found_by_both_paths_appears_once_as_lexical() -> None:
    merged = merge_candidates(
        [_c("a", "lexical")], [_c("a", "vector"), _c("b", "vector")], limit=10
    )

    assert [c.provision_id for c in merged] == ["a", "b"]
    assert merged[0].origin == "lexical"


def test_the_limit_is_honoured() -> None:
    merged = merge_candidates([_c("a", "lexical")], [_c("b", "vector"), _c("c", "vector")], limit=2)

    assert [c.provision_id for c in merged] == ["a", "b"]


def test_no_lexical_hits_leaves_vector_order_untouched() -> None:
    vector = [_c("b", "vector"), _c("c", "vector")]

    assert merge_candidates([], vector, limit=10) == vector
