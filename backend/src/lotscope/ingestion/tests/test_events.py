from lotscope.ingestion.events import (
    CODE_DELINQUENT,
    CODE_SHERIFF_SALE,
    CODE_TAX_UP,
    TaxSnapshot,
    diff_tax,
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
