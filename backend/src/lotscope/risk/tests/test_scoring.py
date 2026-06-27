from lotscope.risk.scoring import (
    LiSignal,
    RiskSignals,
    TaxSignal,
    assess_risk,
)


def _codes(signals: RiskSignals) -> set[str]:
    return {flag.code for flag in assess_risk(signals).flags}


def test_clean_parcel_has_no_flags() -> None:
    result = assess_risk(RiskSignals(li=LiSignal(), tax=TaxSignal(False, 0, 0, False)))
    assert result.flags == []
    assert result.risk_score == 0.0
    assert result.summary == "No major risk flags found."
    assert result.confidence == "high"


def test_sheriff_sale_and_delinquency_flagged() -> None:
    signals = RiskSignals(
        li=LiSignal(),
        tax=TaxSignal(is_delinquent=True, total_due=25000, years_owed=4, in_sheriff_sale=True),
    )
    result = assess_risk(signals)
    codes = {flag.code for flag in result.flags}
    assert {"sheriff_sale", "tax_delinquency"} <= codes
    assert any(flag.severity == "high" for flag in result.flags)
    assert result.risk_score > 0


def test_small_delinquency_is_medium() -> None:
    signals = RiskSignals(
        li=LiSignal(),
        tax=TaxSignal(is_delinquent=True, total_due=500, years_owed=1, in_sheriff_sale=False),
    )
    flag = next(f for f in assess_risk(signals).flags if f.code == "tax_delinquency")
    assert flag.severity == "medium"


def test_imminently_dangerous_dominates_unsafe() -> None:
    signals = RiskSignals(li=LiSignal(has_unsafe=True, has_imminently_dangerous=True, violations=5))
    codes = _codes(signals)
    assert "imminently_dangerous" in codes
    assert "unsafe_structure" not in codes
    assert "li_violations" in codes


def test_high_risk_flood_zone_is_high_severity() -> None:
    result = assess_risk(RiskSignals(li=LiSignal(), flood_zones=["AE"]))
    flood = next(f for f in result.flags if f.code == "flood_zone")
    assert flood.severity == "high"


def test_x_flood_zone_is_medium() -> None:
    result = assess_risk(RiskSignals(li=LiSignal(), flood_zones=["X"]))
    flood = next(f for f in result.flags if f.code == "flood_zone")
    assert flood.severity == "medium"


def test_city_owned_is_flagged() -> None:
    result = assess_risk(RiskSignals(li=LiSignal(), is_city_owned=True))
    assert "public_ownership" in {f.code for f in result.flags}


def test_missing_tax_data_lowers_confidence() -> None:
    result = assess_risk(RiskSignals(li=LiSignal(), tax=None))
    assert result.confidence == "medium"


def test_risk_score_is_capped_at_100() -> None:
    signals = RiskSignals(
        li=LiSignal(has_imminently_dangerous=True, violations=9, demolitions=2),
        tax=TaxSignal(is_delinquent=True, total_due=99999, years_owed=10, in_sheriff_sale=True),
        is_city_owned=True,
        flood_zones=["AE"],
    )
    assert assess_risk(signals).risk_score == 100.0
