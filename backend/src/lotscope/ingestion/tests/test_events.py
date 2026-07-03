import pytest

from lotscope.ingestion.events import (
    CODE_ASSESSMENT,
    CODE_DANGER,
    CODE_DELINQUENT,
    CODE_LI_NEW,
    CODE_NEW_DEED,
    CODE_NEW_DEMO,
    CODE_NEW_PERMIT,
    CODE_SHERIFF_SALE,
    CODE_TAX_UP,
    SEVERITY_LOW,
    TaxSnapshot,
    classify_li_event,
    diff_assessment,
    diff_tax,
    new_deed_event,
)


def _snap(delinquent: bool | None, total_due: float | None, sheriff: bool | None) -> TaxSnapshot:
    return TaxSnapshot(is_delinquent=delinquent, total_due=total_due, in_sheriff_sale=sheriff)


def test_no_prior_core_row_emits_nothing() -> None:
    assert diff_tax(None, _snap(True, 5000, True)) == []


def test_unchanged_emits_nothing() -> None:
    same = _snap(True, 5000, False)
    assert diff_tax(same, same) == []


def test_new_sheriff_sale_and_delinquency_emit_high_events() -> None:
    old = _snap(False, 0, False)
    new = _snap(True, 5000, True)
    codes = {d.code for d in diff_tax(old, new)}
    assert CODE_SHERIFF_SALE in codes
    assert CODE_DELINQUENT in codes
    assert CODE_TAX_UP in codes


def test_rising_total_due_alone_emits_tax_up() -> None:
    drafts = diff_tax(_snap(True, 1000, False), _snap(True, 3000, False))
    assert [d.code for d in drafts] == [CODE_TAX_UP]
    assert drafts[0].new_value == {"total_due": 3000}


def test_cleared_flag_does_not_emit() -> None:
    assert diff_tax(_snap(True, 5000, True), _snap(False, 5000, False)) == []


@pytest.mark.parametrize(
    ("event_type", "unsafe", "dangerous", "expected"),
    [
        ("violation", False, False, CODE_LI_NEW),
        ("violation", True, False, CODE_DANGER),
        ("violation", False, True, CODE_DANGER),
        ("permit", None, None, CODE_NEW_PERMIT),
        ("demolition", None, None, CODE_NEW_DEMO),
    ],
)
def test_classify_li_event(
    event_type: str, unsafe: bool | None, dangerous: bool | None, expected: str
) -> None:
    draft = classify_li_event(event_type, unsafe, dangerous)
    assert draft is not None
    assert draft.code == expected


def test_classify_li_event_unknown_type_is_none() -> None:
    assert classify_li_event("inspection", None, None) is None


def test_new_deed_event_builds_low_severity_draft() -> None:
    draft = new_deed_event("DOC-1", 150000.0)
    assert draft.code == CODE_NEW_DEED
    assert draft.severity == SEVERITY_LOW
    assert draft.old_value is None
    assert draft.new_value == {"document_id": "DOC-1", "sale_price": 150000.0}


@pytest.mark.parametrize(
    ("old", "new", "expected_code"),
    [
        (None, 100000.0, None),
        (100000.0, None, None),
        (100000.0, 100000.0, None),
        (100000.0, 80000.0, CODE_ASSESSMENT),
        (100000.0, 130000.0, CODE_ASSESSMENT),
    ],
)
def test_diff_assessment(old: float | None, new: float | None, expected_code: str | None) -> None:
    draft = diff_assessment(old, new)
    assert (draft.code if draft else None) == expected_code
