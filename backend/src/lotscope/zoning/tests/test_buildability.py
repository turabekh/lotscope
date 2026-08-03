from lotscope.zoning.buildability import (
    DistrictStandard,
    ParcelDimensions,
    assess_buildability,
    by_right_unit_count,
    estimate_density_units,
    far_unit_estimate,
)


def _far_district(**overrides: object) -> DistrictStandard:
    base = {
        "code": "RM-4",
        "code_version": "2024-01",
        "permitted_uses": ["single_family", "two_family", "multi_family"],
        "max_floor_area_ratio_pct": 350.0,
    }
    base.update(overrides)
    return DistrictStandard(**base)  # type: ignore[arg-type]


def test_far_unit_estimate_from_floor_area() -> None:
    assert far_unit_estimate(_far_district(), 2500.0) == 7
    assert far_unit_estimate(_far_district(), None) is None


def test_far_unit_estimate_requires_multi_family_and_no_master_plan() -> None:
    assert far_unit_estimate(_far_district(permitted_uses=["commercial"]), 2500.0) is None
    assert far_unit_estimate(_far_district(requires_master_plan=True), 2500.0) is None


def test_estimate_density_prefers_per_unit_then_far_then_cap() -> None:
    assert estimate_density_units(_far_district(lot_area_per_unit_sqft=480.0), 5000.0) == (
        10,
        "per_unit",
    )
    assert estimate_density_units(_far_district(), 5000.0) == (15, "far_estimate")
    flat = DistrictStandard(
        code="X", code_version="v", permitted_uses=["multi_family"], max_units=4
    )
    assert estimate_density_units(flat, 5000.0) == (4, "flat_cap")


def _rm1(**overrides: object) -> DistrictStandard:
    base = {
        "code": "RM-1",
        "code_version": "2024-01",
        "permitted_uses": ["single_family", "two_family", "multi_family"],
        "min_lot_area_sqft": 1440.0,
        "max_height_ft": 38.0,
        "lot_area_per_unit_sqft": 480.0,
    }
    base.update(overrides)
    return DistrictStandard(**base)  # type: ignore[arg-type]


def test_density_units_scale_with_lot_area() -> None:
    assert by_right_unit_count(_rm1(), 480.0) == 1
    assert by_right_unit_count(_rm1(), 1440.0) == 3
    assert by_right_unit_count(_rm1(), 5000.0) == 10


def test_density_units_floor_at_one_when_area_present() -> None:
    assert by_right_unit_count(_rm1(), 300.0) == 1


def test_density_falls_back_to_flat_cap_without_density_rule() -> None:
    standard = _rm1(lot_area_per_unit_sqft=None, max_units=4)
    assert by_right_unit_count(standard, 5000.0) == 4


def test_density_requires_multi_family_use() -> None:
    standard = _rm1(permitted_uses=["single_family"], max_units=1)
    assert by_right_unit_count(standard, 5000.0) == 1


def test_assess_buildability_uses_density_units() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=2880.0, lot_width_ft=18.0, depth_ft=90.0), _rm1()
    )
    assert result.by_right_units == 6


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


def test_fully_known_lot_reports_no_critical_unknowns() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90), _rsa5()
    )
    assert result.critical_unknowns == ()
    assert result.confidence == "high"


def test_missing_height_standard_blocks_high_confidence() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90),
        _rsa5(max_height_ft=None),
    )
    assert "height_standard_missing" in result.critical_unknowns
    assert result.confidence == "medium"


def test_coverage_estimated_footprint_blocks_high_confidence() -> None:
    standard = _rsa5(
        front_setback_ft=None,
        rear_setback_ft=None,
        side_setback_ft=None,
        max_occupancy_pct=75.0,
    )
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90), standard
    )
    assert result.buildable_area_sqft == 1200.0
    assert "footprint_not_setback_derived" in result.critical_unknowns
    assert result.confidence == "medium"


def test_missing_permitted_uses_blocks_high_confidence() -> None:
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=1600, lot_width_ft=18, depth_ft=90),
        _rsa5(permitted_uses=[]),
    )
    assert "permitted_uses_missing" in result.critical_unknowns
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


def test_an_unregulated_height_is_not_a_critical_unknown() -> None:
    standard = _rsa5(
        code="CMX-4",
        max_height_ft=None,
        field_dispositions={"max_height_ft": {"disposition": "unregulated"}},
    )
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=15592, lot_width_ft=66, depth_ft=200), standard
    )

    assert "height_standard_missing" not in result.critical_unknowns


def test_a_conditional_height_remains_a_critical_unknown() -> None:
    standard = _rsa5(
        code="I-1",
        max_height_ft=None,
        field_dispositions={
            "max_height_ft": {"disposition": "conditional", "note": "60 ft. where abutting"}
        },
    )
    result = assess_buildability(
        ParcelDimensions(lot_area_sqft=15592, lot_width_ft=66, depth_ft=200), standard
    )

    assert "height_standard_missing" in result.critical_unknowns
