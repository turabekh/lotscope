import pytest

from lotscope.risk.scoring import (
    AccessSignal,
    LiSignal,
    RiskSignals,
    TaxSignal,
    TitleSignal,
    assess_risk,
)


def _codes(signals: RiskSignals) -> set[str]:
    return {flag.code for flag in assess_risk(signals).flags}


def _title_codes(owner: str | None) -> set[str]:
    return _codes(RiskSignals(li=LiSignal(), title=TitleSignal(owner=owner)))


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


def test_li_violation_detail_includes_types_and_open_count() -> None:
    signals = RiskSignals(
        li=LiSignal(
            violations=3,
            open_violations=2,
            violation_types=("DANGEROUS", "INTERIOR"),
        )
    )
    flag = next(f for f in assess_risk(signals).flags if f.code == "li_violations")
    assert flag.detail == "3 violation(s) on record, 2 still open — Dangerous, Interior."
    assert flag.severity == "medium"


def test_li_violation_detail_without_types_stays_generic() -> None:
    flag = next(
        f
        for f in assess_risk(RiskSignals(li=LiSignal(violations=1))).flags
        if f.code == "li_violations"
    )
    assert flag.detail == "1 violation(s) on record."


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


@pytest.mark.parametrize(
    "owner",
    [
        "AGHOIAN GREGORY K ESTATE OF",
        "MYERS THURMAN ESTATE",
        "STERLING HEIRS TRUST",
        "SMITH JOHN HEIR",
        "JONES MARY DECEASED",
        "WILLIAMS ROBERT DECD",
    ],
)
def test_estate_owner_flagged(owner: str) -> None:
    codes = _title_codes(owner)
    assert "estate_owner" in codes


@pytest.mark.parametrize(
    "owner",
    [
        "URBAN REAL ESTATE INVESTMENTS LLC",
        "ACME HOLDINGS LLC",
        "SMITH JOHN",
        "GRANT ESTATE LLC",
        "JLS ESTATE PARTNERS LLC",
        "REAL DEAL ESTATE LLC",
        "BRESNENI ESTATE LLC",
        None,
        "",
    ],
)
def test_non_estate_owner_not_flagged(owner: str | None) -> None:
    assert "estate_owner" not in _title_codes(owner)


def test_estate_owner_severity_is_medium() -> None:
    signals = RiskSignals(li=LiSignal(), title=TitleSignal(owner="DALE MATTIE ESTATE OF"))
    flag = next(f for f in assess_risk(signals).flags if f.code == "estate_owner")
    assert flag.severity == "medium"
    assert flag.source == "parcel"


def test_multiple_owners_flagged() -> None:
    codes = _title_codes("MICKENS ARTHUR ET AL")
    assert "multiple_owners" in codes
    assert _title_codes("BROWN SUSAN ET UX") == {"multiple_owners"}


def test_missing_title_signal_adds_no_flags() -> None:
    assert _codes(RiskSignals(li=LiSignal(), title=None)) == set()


def test_no_street_frontage_is_flagged() -> None:
    signals = RiskSignals(
        li=LiSignal(), access=AccessSignal(has_geometry=True, has_street_frontage=False)
    )
    flag = next(f for f in assess_risk(signals).flags if f.code == "no_street_access")
    assert flag.severity == "low"
    assert flag.source == "street_centerline"


def test_street_frontage_is_not_flagged() -> None:
    signals = RiskSignals(
        li=LiSignal(), access=AccessSignal(has_geometry=True, has_street_frontage=True)
    )
    assert "no_street_access" not in _codes(signals)


def test_no_geometry_does_not_flag_access() -> None:
    signals = RiskSignals(
        li=LiSignal(), access=AccessSignal(has_geometry=False, has_street_frontage=False)
    )
    assert "no_street_access" not in _codes(signals)


def test_risk_score_is_capped_at_100() -> None:
    signals = RiskSignals(
        li=LiSignal(has_imminently_dangerous=True, violations=9, demolitions=2),
        tax=TaxSignal(is_delinquent=True, total_due=99999, years_owed=10, in_sheriff_sale=True),
        is_city_owned=True,
        flood_zones=["AE"],
    )
    assert assess_risk(signals).risk_score == 100.0
