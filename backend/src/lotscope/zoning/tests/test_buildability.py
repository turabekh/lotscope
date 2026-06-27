from lotscope.zoning.buildability import (
    DistrictStandard,
    ParcelDimensions,
    assess_buildability,
)


def _rsa5(**overrides: object) -> DistrictStandard:
    base = {
        "code": "RSA-5",
        "code_version": "2024-01",
        "permitted_uses": ["single_family"],
        "min_lot_area_sqft": 1440.0,
        "min_lot_width_ft": 16.0,
        "max_height_ft": 38.0,
        "max_units": 1,
        "front_setback_ft": 0.0,
        "rear_setback_ft": 9.0,
        "side_setback_ft": 0.0,
    }
    base.update(overrides)
    return DistrictStandard(**base)  # type: ignore[arg-type]


def test_conforming_lot_is_buildable_by_right() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90), _rsa5()
    )
    assert result.conforming is True
    assert result.can_build_by_right is True
    assert result.needs_variance is False
    assert result.by_right_units == 1
    assert result.max_height_ft == 38.0
    assert result.confidence == "high"
    assert result.buildability_score == 100.0
    assert result.cited_section == "RSA-5 (Title 14, 2024-01)"


def test_undersized_lot_is_non_conforming_and_needs_variance() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1000, lot_width_ft=14, depth_ft=70), _rsa5()
    )
    assert result.conforming is False
    assert result.needs_variance is True
    assert result.can_build_by_right is False
    assert any("below the 1440 sqft minimum" in reason for reason in result.reasons)
    assert any("variance" in reason.lower() for reason in result.reasons)
    assert result.buildability_score < 100.0


def test_unknown_dimensions_yield_unknown_conformance() -> None:
    result = assess_buildability(ParcelDimensions(), _rsa5())
    assert result.conforming is None
    assert result.needs_variance is None
    assert result.can_build_by_right is False
    assert result.confidence == "low"


def test_district_without_minimums_is_conforming() -> None:
    standard = _rsa5(min_lot_area_sqft=None, min_lot_width_ft=None)
    result = assess_buildability(ParcelDimensions(), standard)
    assert result.conforming is True
    assert result.can_build_by_right is True


def test_buildable_area_from_setbacks() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90), _rsa5()
    )
    assert result.buildable_area_sqft == 1458.0


def test_buildable_area_from_occupancy_when_no_setback_geometry() -> None:
    standard = _rsa5(
        front_setback_ft=None,
        rear_setback_ft=None,
        side_setback_ft=None,
        max_occupancy_pct=75.0,
    )
    result = assess_buildability(ParcelDimensions(lot_area_sqft=2000), standard)
    assert result.buildable_area_sqft == 1500.0


def test_no_permitted_uses_blocks_by_right() -> None:
    standard = _rsa5(permitted_uses=[])
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90), standard
    )
    assert result.can_build_by_right is False
    assert any("permitted uses" in reason.lower() for reason in result.reasons)


def test_partial_dimensions_give_medium_confidence() -> None:
    result = assess_buildability(ParcelDimensions(lot_area_sqft=1600), _rsa5())
    assert result.confidence == "medium"


def test_master_plan_district_is_not_by_right() -> None:
    standard = _rsa5(
        code="SP-INS",
        permitted_uses=["institutional"],
        min_lot_area_sqft=None,
        min_lot_width_ft=None,
        max_units=None,
        requires_master_plan=True,
    )
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=200000, lot_width_ft=300, depth_ft=400), standard
    )
    assert result.requires_master_plan is True
    assert result.can_build_by_right is False
    assert result.by_right_units is None
    assert any("master plan" in reason.lower() for reason in result.reasons)
    assert result.buildability_score == 25.0
