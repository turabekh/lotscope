from datetime import date

import pytest

from lotscope.valuation.avm import (
    Comp,
    estimate_land_value,
    land_use_class,
    price_per_sqft,
    trim_outlier_rates,
)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("RSA5", "residential"),
        ("RM-1", "residential"),
        ("RMX-3", "residential"),
        ("CMX2", "commercial"),
        ("CA-1", "commercial"),
        ("I-2", "industrial"),
        ("ICMX", "industrial"),
        ("IRMX", "industrial"),
        ("SP-INS", "special"),
        ("", None),
        (None, None),
        ("ZZ9", None),
    ],
)
def test_land_use_class(code: str | None, expected: str | None) -> None:
    assert land_use_class(code) == expected


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


def test_trim_outlier_rates_drops_points_beyond_iqr_fence() -> None:
    kept, removed = trim_outlier_rates([98.0, 100.0, 101.0, 99.0, 102.0, 5000.0])
    assert removed == 1
    assert 5000.0 not in kept


def test_trim_outlier_rates_keeps_small_samples_intact() -> None:
    rates = [10.0, 1000.0, 20.0]
    kept, removed = trim_outlier_rates(rates)
    assert removed == 0
    assert kept == rates


def test_trim_outlier_rates_keeps_genuine_spread() -> None:
    rates = [40.0, 60.0, 100.0, 220.0, 300.0]
    _, removed = trim_outlier_rates(rates)
    assert removed == 0


def test_estimate_trims_per_sqft_outlier_to_tighten_range() -> None:
    comps = [_comp(rate) for rate in (98, 100, 101, 99, 102, 5000)]
    result = estimate_land_value(2000.0, comps)
    assert result.estimate == 200000.0
    assert result.high is not None
    assert result.high <= 210000.0
    assert result.comp_count == 6
    assert any("outlier" in reason.lower() for reason in result.reasons)
    assert result.confidence == "high"
