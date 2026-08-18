from lotscope.risk.violation_status import is_open_violation, open_violation_sql


def test_an_open_violation_on_a_live_case_is_open() -> None:
    assert is_open_violation("OPEN", "IN VIOLATION") is True
    assert is_open_violation("OPEN", "IN VIOLATION - COURT") is True


def test_a_complied_violation_is_not_open_however_its_case_reads() -> None:
    assert is_open_violation("COMPLIED", "CLOSED") is False
    assert is_open_violation("COMPLIED", "IN VIOLATION") is False


def test_the_issued_notice_states_are_not_open() -> None:
    for status in ("SVN ISSUED", "CVN ISSUED", "WARNING ISSUED"):
        assert is_open_violation(status, "SVN ISSUED, BALANCE DUE") is False


def test_a_closed_case_overrides_an_open_violation_row() -> None:
    assert is_open_violation("OPEN", "CLOSED") is False


def test_an_unknown_case_status_does_not_close_an_open_violation() -> None:
    assert is_open_violation("OPEN", None) is True
    assert is_open_violation("OPEN", "") is True


def test_matching_ignores_case_and_padding() -> None:
    assert is_open_violation("  open ", " in violation ") is True


def test_a_missing_violation_status_is_not_open() -> None:
    assert is_open_violation(None, "IN VIOLATION") is False


def test_the_sql_fragment_encodes_the_same_rule() -> None:
    sql = open_violation_sql("e")

    assert "upper(coalesce(e.status, '')) = 'OPEN'" in sql
    assert "upper(coalesce(e.case_status, '')) NOT IN ('CLOSED')" in sql
