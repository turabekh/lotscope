import pytest

from lotscope.risk.scoring import (
    AccessSignal,
    HistoricSignal,
    LiSignal,
    OverlaySignal,
    RcoSignal,
    RiskFlag,
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


def _flood_flag_for(zones: list[str]) -> RiskFlag | None:
    result = assess_risk(RiskSignals(li=LiSignal(), flood_zones=zones))
    return next((f for f in result.flags if f.code == "flood_zone"), None)


@pytest.mark.parametrize("zone", ["A", "AE", "AH", "AO", "AR", "A99", "V", "VE"])
def test_sfha_flood_zones_flag_high(zone: str) -> None:
    flood = _flood_flag_for([zone])
    assert flood is not None
    assert flood.severity == "high"
    assert zone in flood.detail


@pytest.mark.parametrize("zone", ["X", "C", "OPEN WATER", "AREA OF MINIMAL FLOOD HAZARD"])
def test_minimal_flood_zones_are_not_flagged(zone: str) -> None:
    assert _flood_flag_for([zone]) is None


@pytest.mark.parametrize("zone", ["X (SHADED)", "0.2 PCT ANNUAL CHANCE FLOOD HAZARD", "B"])
def test_moderate_flood_zones_are_info_only(zone: str) -> None:
    flood = _flood_flag_for([zone])
    assert flood is not None
    assert flood.severity == "info"


def test_moderate_flood_zone_adds_no_risk_weight() -> None:
    baseline = assess_risk(RiskSignals(li=LiSignal(), flood_zones=[])).risk_score
    with_moderate = assess_risk(RiskSignals(li=LiSignal(), flood_zones=["X (SHADED)"])).risk_score
    assert with_moderate == baseline


def test_mixed_zones_flag_only_sfha_in_detail() -> None:
    flood = _flood_flag_for(["X", "AE"])
    assert flood is not None
    assert flood.severity == "high"
    assert "AE" in flood.detail
    assert "X" not in flood.detail


def test_no_flood_zones_no_flag() -> None:
    assert _flood_flag_for([]) is None


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


def test_no_street_data_for_market_does_not_flag_access() -> None:
    signals = RiskSignals(
        li=LiSignal(),
        access=AccessSignal(
            has_geometry=True, has_street_frontage=False, street_data_available=False
        ),
    )
    assert "no_street_access" not in _codes(signals)


def test_historic_district_is_flagged() -> None:
    signals = RiskSignals(
        li=LiSignal(),
        historic=HistoricSignal(in_district=True, district_name="Society Hill"),
    )
    flag = next(f for f in assess_risk(signals).flags if f.code == "historic_district")
    assert flag.severity == "low"
    assert flag.source == "historicdistricts_local"
    assert "Society Hill" in flag.detail


def test_historic_district_without_name_is_still_flagged() -> None:
    signals = RiskSignals(li=LiSignal(), historic=HistoricSignal(in_district=True))
    assert "historic_district" in _codes(signals)


def test_parcel_outside_historic_district_not_flagged() -> None:
    signals = RiskSignals(li=LiSignal(), historic=HistoricSignal(in_district=False))
    assert "historic_district" not in _codes(signals)


def test_missing_historic_signal_adds_no_flag() -> None:
    assert "historic_district" not in _codes(RiskSignals(li=LiSignal(), historic=None))


def test_risk_score_is_capped_at_100() -> None:
    signals = RiskSignals(
        li=LiSignal(has_imminently_dangerous=True, violations=9, demolitions=2),
        tax=TaxSignal(is_delinquent=True, total_due=99999, years_owed=10, in_sheriff_sale=True),
        is_city_owned=True,
        flood_zones=["AE"],
    )
    assert assess_risk(signals).risk_score == 100.0


def test_overlay_district_flag_lists_names() -> None:
    signals = RiskSignals(li=LiSignal(), overlays=OverlaySignal(overlay_names=("/NCA", "/CTR")))
    flag = next(f for f in assess_risk(signals).flags if f.code == "overlay_district")
    assert flag.severity == "low"
    assert "/NCA" in flag.detail
    assert "/CTR" in flag.detail


def test_rco_flag_lists_name() -> None:
    signals = RiskSignals(li=LiSignal(), rco=RcoSignal(rco_names=("Girard Estate Neighbors",)))
    flag = next(f for f in assess_risk(signals).flags if f.code == "rco")
    assert flag.severity == "low"
    assert "Girard Estate Neighbors" in flag.detail


def test_no_overlay_or_rco_when_empty() -> None:
    codes = _codes(RiskSignals(li=LiSignal(), overlays=OverlaySignal(), rco=RcoSignal()))
    assert "overlay_district" not in codes
    assert "rco" not in codes
