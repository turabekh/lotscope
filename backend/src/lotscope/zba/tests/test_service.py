from lotscope.zba.service import summarize_decisions


def test_summarize_counts_proviso_grants_as_grants() -> None:
    granted, decided = summarize_decisions(
        {"GRANTED": 5, "GRANTED/PROV": 3, "DENIED": 2, "DENIED/PROV": 1}
    )
    assert granted == 8
    assert decided == 11


def test_summarize_excludes_non_decisive_outcomes() -> None:
    granted, decided = summarize_decisions(
        {"GRANTED": 4, "WITHDRAWN": 9, "DISMISSED": 3, "CONTINUED": 2, "HELD": 1}
    )
    assert granted == 4
    assert decided == 4


def test_summarize_empty_is_zero() -> None:
    assert summarize_decisions({}) == (0, 0)


def _pct(granted: int, decided: int) -> float:
    return round(granted / decided, 3)


def test_grant_rate_math_matches_expected_ratio() -> None:
    granted, decided = summarize_decisions({"GRANTED": 7, "GRANTED/PROV": 1, "DENIED": 2})
    assert _pct(granted, decided) == 0.8
