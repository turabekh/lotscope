from lotscope.ingestion.loaders.tax import TaxRecord, to_tax_row
from lotscope.risk.scoring import TaxSignal, _tax_flags
from lotscope.verdict.composition import compose_verdict


def test_an_unknown_amount_owed_is_not_recorded_as_not_delinquent() -> None:
    row = to_tax_row(TaxRecord(opa_number="1234567", total_due=None))
    assert row is not None
    assert row["is_delinquent"] is None


def test_a_zero_balance_is_recorded_as_not_delinquent() -> None:
    row = to_tax_row(TaxRecord(opa_number="1234567", total_due=0.0))
    assert row is not None
    assert row["is_delinquent"] is False


def test_a_positive_balance_is_recorded_as_delinquent() -> None:
    row = to_tax_row(TaxRecord(opa_number="1234567", total_due=1500.0))
    assert row is not None
    assert row["is_delinquent"] is True


def test_a_delinquent_parcel_with_an_unreported_amount_does_not_display_zero_owed() -> None:
    flags = _tax_flags(TaxSignal(is_delinquent=True, total_due=None, years_owed=None,
                                 in_sheriff_sale=False))
    delinquency = [flag for flag in flags if flag.code == "tax_delinquency"]
    assert delinquency
    assert "$0" not in delinquency[0].detail
    assert "not reported" in delinquency[0].detail


def test_an_unknown_tax_status_raises_no_delinquency_flag_and_invents_no_clearance() -> None:
    flags = _tax_flags(TaxSignal(is_delinquent=None, total_due=None, years_owed=None,
                                 in_sheriff_sale=False))
    assert [flag.code for flag in flags if flag.code == "tax_delinquency"] == []


def test_a_verdict_with_no_inputs_reports_no_confident_field() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    for name, provenance in composed.field_trust.items():
        assert provenance.status == "unavailable", name
    assert composed.recommendation == "insufficient_data"


def test_a_verdict_with_no_inputs_never_reports_zero_for_a_money_field() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    for field_name in (
        "value_estimate_low",
        "value_estimate_high",
        "arv",
        "est_profit",
        "max_allowable_offer",
        "assessment_market_gap",
    ):
        assert getattr(composed, field_name) is None, field_name


def test_a_verdict_with_no_inputs_never_claims_buildable() -> None:
    composed = compose_verdict(None, None, None, None, assessed_market_value=None)
    assert composed.can_build_by_right is None
    assert composed.by_right_units is None
    assert composed.needs_variance is None
