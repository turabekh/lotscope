from lotscope.compare.service import dedupe_preserve_order


def test_dedupe_keeps_first_occurrence_order() -> None:
    assert dedupe_preserve_order(["b", "a", "b", "c"], 4) == ["b", "a", "c"]


def test_dedupe_caps_at_limit() -> None:
    assert dedupe_preserve_order(["a", "b", "c", "d", "e"], 4) == ["a", "b", "c", "d"]


def test_dedupe_caps_before_counting_duplicates() -> None:
    assert dedupe_preserve_order(["a", "a", "b", "c", "d", "e"], 4) == ["a", "b", "c", "d"]


def test_dedupe_empty() -> None:
    assert dedupe_preserve_order([], 4) == []
