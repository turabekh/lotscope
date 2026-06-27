from datetime import date

from lotscope.valuation.avm import Comp, estimate_land_value, price_per_sqft


def _comp(rate: float, distance: float = 100.0) -> Comp:
    return Comp(
        parcel_number="x",
        distance_ft=distance,
        sale_price=rate * 1000,
        sale_date=date(2024, 1, 1),
        lot_area_sqft=1000.0,
        price_per_sqft=rate,
    )


def test_price_per_sqft_guards_zero_area() -> None:
    assert price_per_sqft(100000, 1000) == 100.0
    assert price_per_sqft(100000, 0) is None
    assert price_per_sqft(100000, None) is None


def test_tight_cluster_of_comps_is_high_confidence() -> None:
    comps = [_comp(rate) for rate in (98, 100, 101, 99, 102)]
    result = estimate_land_value(2000.0, comps)
    assert result.confidence == "high"
    assert result.estimate == 200000.0
    assert result.coefficient_of_variation is not None
    assert result.coefficient_of_variation < 0.25


def test_wide_spread_lowers_confidence() -> None:
    comps = [_comp(rate) for rate in (40, 100, 220, 60, 300)]
    result = estimate_land_value(2000.0, comps)
    assert result.confidence == "low"
    assert result.low is not None
    assert result.high is not None
    assert result.low < result.estimate < result.high  # type: ignore[operator]


def test_few_comps_are_medium_at_best() -> None:
    comps = [_comp(rate) for rate in (100, 105, 95)]
    result = estimate_land_value(1000.0, comps)
    assert result.confidence in {"medium", "low"}


def test_no_comps_yields_unknown() -> None:
    result = estimate_land_value(2000.0, [])
    assert result.estimate is None
    assert result.confidence == "low"
    assert result.comp_count == 0


def test_unknown_subject_area_yields_unknown() -> None:
    comps = [_comp(100)]
    result = estimate_land_value(None, comps)
    assert result.estimate is None
    assert "lot area" in result.reasons[0].lower()
