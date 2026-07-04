from datetime import date

import pytest

from lotscope.valuation.avm import (
    Comp,
    estimate_land_value,
    is_related_party,
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


def test_percentile_range_clips_extreme_high_when_depth_allows() -> None:
    comps = [_comp(rate) for rate in (40, 60, 100, 220, 300)]
    result = estimate_land_value(1000.0, comps)
    assert result.high is not None
    assert result.high < 300 * 1000
    assert result.estimate == 100 * 1000
    assert any("10th-90th percentile of 5 comparable" in reason for reason in result.reasons)


def test_full_range_preserved_for_shallow_comp_sets() -> None:
    comps = [_comp(rate) for rate in (95, 100, 105)]
    result = estimate_land_value(1000.0, comps)
    assert result.low == 95 * 1000
    assert result.high == 105 * 1000
    assert result.estimate == 100 * 1000
    assert any("full range of 3 comp" in reason for reason in result.reasons)


@pytest.mark.parametrize(
    ("grantor", "grantee", "expected"),
    [
        ("SMITH JOHN", "SMITH JANE", True),
        ("SMITH JOHN JR", "SMITH JOHN SR", True),
        ("SMITH JOHN & SMITH JANE", "SMITH JANE", True),
        ("THE ABC TRUST", "ABC HOLDINGS LLC", True),
        ("JOHNSON MARY", "WILLIAMS ROBERT", False),
        ("ACME LLC", "BETA INC", False),
        ("A B", "A B", False),
        (None, "SMITH JOHN", False),
        ("SMITH JOHN", None, False),
        ("", "", False),
    ],
)
def test_is_related_party(grantor: str | None, grantee: str | None, expected: bool) -> None:
    assert is_related_party(grantor, grantee) is expected


def test_is_related_party_is_symmetric_and_self_related() -> None:
    a, b = "OCONNOR PATRICK", "SULLIVAN ERIN"
    assert is_related_party(a, b) == is_related_party(b, a)
    assert is_related_party(a, a) is True


def test_estimate_reports_related_party_exclusions() -> None:
    comps = [_comp(rate) for rate in (98, 100, 101, 99)]
    result = estimate_land_value(2000.0, comps, related_party_excluded=2)
    assert any("related-party" in reason.lower() for reason in result.reasons)


def test_estimate_omits_related_party_reason_when_none_excluded() -> None:
    comps = [_comp(rate) for rate in (98, 100, 101, 99)]
    result = estimate_land_value(2000.0, comps)
    assert not any("related-party" in reason.lower() for reason in result.reasons)
