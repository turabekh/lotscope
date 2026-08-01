from lotscope.watchlist.changes import compute_changes

_BASE = {
    "is_vacant": True,
    "market_value": 100000.0,
    "opportunity_score": 60,
    "is_delinquent": False,
    "total_due": 0.0,
    "in_sheriff_sale": False,
    "violations": 1,
    "dangerous": False,
    "distress_score": 20,
}


def test_no_snapshot_yields_no_changes() -> None:
    assert compute_changes(None, _BASE) == []


def test_identical_state_yields_no_changes() -> None:
    assert compute_changes(dict(_BASE), dict(_BASE)) == []


def test_new_sheriff_sale_is_high() -> None:
    current = {**_BASE, "in_sheriff_sale": True}
    changes = compute_changes(_BASE, current)
    assert any(c.code == "sheriff_sale" and c.severity == "high" for c in changes)


def test_tax_increase_and_new_delinquency() -> None:
    current = {**_BASE, "is_delinquent": True, "total_due": 5000.0}
    codes = {c.code for c in compute_changes(_BASE, current)}
    assert "delinquent" in codes
    assert "tax_up" in codes


def test_new_violations_and_danger() -> None:
    current = {**_BASE, "violations": 3, "dangerous": True}
    changes = compute_changes(_BASE, current)
    by_code = {c.code: c for c in changes}
    assert "li_new" in by_code
    assert "2 new" in by_code["li_new"].label
    assert by_code["danger"].severity == "high"


def test_score_and_assessment_moves_are_info() -> None:
    current = {**_BASE, "opportunity_score": 72, "market_value": 90000.0, "distress_score": 35}
    by_code = {c.code: c for c in compute_changes(_BASE, current)}
    assert by_code["opportunity"].label == "Opportunity 60 → 72"
    assert by_code["assessment"].severity == "info"
    assert by_code["distress"].severity == "medium"


def test_distress_decrease_is_not_flagged() -> None:
    current = {**_BASE, "distress_score": 10}
    assert all(c.code != "distress" for c in compute_changes(_BASE, current))


def test_opportunity_change_records_which_way_it_moved() -> None:
    dropped = compute_changes({"opportunity_score": 54}, {"opportunity_score": 46})
    assert [(c.code, c.direction) for c in dropped] == [("opportunity", "down")]

    rose = compute_changes({"opportunity_score": 46}, {"opportunity_score": 54})
    assert [(c.code, c.direction) for c in rose] == [("opportunity", "up")]


def test_distress_change_records_which_way_it_moved() -> None:
    rose = compute_changes({"distress_score": 65}, {"distress_score": 75})
    assert [(c.code, c.direction) for c in rose] == [("distress", "up")]


def test_a_change_with_no_direction_says_so_rather_than_guessing() -> None:
    changes = compute_changes({"in_sheriff_sale": False}, {"in_sheriff_sale": True})
    assert [(c.code, c.direction) for c in changes] == [("sheriff_sale", "none")]
