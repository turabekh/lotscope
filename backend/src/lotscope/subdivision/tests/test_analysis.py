from lotscope.subdivision.analysis import (
    SubdivisionInputs,
    analyze_subdivision,
    small_lot_provision_for,
)

_RSA5_SMALL_LOT = small_lot_provision_for("RSA-5")


def _small_lot_inputs(**overrides: object) -> SubdivisionInputs:
    base: dict[str, object] = {
        "district_code": "RSA-5",
        "lot_area_sqft": 1600.0,
        "lot_width_ft": 20.0,
        "min_lot_area_sqft": 1440.0,
        "min_lot_width_ft": 16.0,
        "small_lot_provision": _RSA5_SMALL_LOT,
        "adjacent_small_share": 0.8,
        "has_overlay": False,
    }
    base.update(overrides)
    return SubdivisionInputs(**base)  # type: ignore[arg-type]


def test_small_lot_provision_splits_qualifying_lot() -> None:
    result = analyze_subdivision(_small_lot_inputs())
    assert result.can_subdivide is True
    assert result.max_lots == 2
    assert result.min_lot_area_sqft == 800.0
    assert any("Small-lot provision applies" in reason for reason in result.reasons)


def test_small_lot_provision_requires_adjacency_share() -> None:
    result = analyze_subdivision(_small_lot_inputs(adjacent_small_share=0.74))
    assert result.can_subdivide is False
    assert result.max_lots == 1
    assert any("at least 75%" in reason for reason in result.reasons)


def test_small_lot_provision_requires_minimum_width() -> None:
    result = analyze_subdivision(_small_lot_inputs(lot_width_ft=14.0))
    assert result.can_subdivide is False
    assert result.max_lots != 2


def test_overlay_blocks_small_lot_division_with_caveat() -> None:
    result = analyze_subdivision(_small_lot_inputs(has_overlay=True))
    assert result.can_subdivide is False
    assert result.max_lots == 1
    assert any("§14-500" in reason for reason in result.reasons)


def _inputs(**overrides: object) -> SubdivisionInputs:
    base: dict[str, object] = {
        "district_code": "RSA-5",
        "lot_area_sqft": 1800.0,
        "lot_width_ft": 18.0,
        "min_lot_area_sqft": 1440.0,
        "min_lot_width_ft": 16.0,
    }
    base.update(overrides)
    return SubdivisionInputs(**base)  # type: ignore[arg-type]


def test_wide_lot_can_subdivide() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=3200.0, lot_width_ft=36.0))
    assert result.can_subdivide is True
    assert result.max_lots == 2
    assert result.is_conforming is True
    assert result.needs_consolidation is False


def test_width_is_limiting_factor() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=10000.0, lot_width_ft=33.0))
    assert result.max_lots == 2
    assert result.limiting_factor == "width"


def test_area_is_limiting_factor() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=3000.0, lot_width_ft=80.0))
    assert result.max_lots == 2
    assert result.limiting_factor == "area"


def test_conforming_but_too_small_to_split() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=1800.0, lot_width_ft=18.0))
    assert result.can_subdivide is False
    assert result.max_lots == 1
    assert result.is_conforming is True
    assert result.needs_consolidation is False


def test_below_minimum_needs_consolidation() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=960.0, lot_width_ft=14.0))
    assert result.can_subdivide is False
    assert result.max_lots == 0
    assert result.is_conforming is False
    assert result.needs_consolidation is True


def test_no_minimums_recorded() -> None:
    result = analyze_subdivision(_inputs(min_lot_area_sqft=None, min_lot_width_ft=None))
    assert result.can_subdivide is False
    assert result.max_lots is None
    assert result.is_conforming is None


def test_unknown_dimensions() -> None:
    result = analyze_subdivision(_inputs(lot_area_sqft=None, lot_width_ft=None))
    assert result.can_subdivide is False
    assert result.max_lots is None


def test_single_known_constraint_uses_what_is_present() -> None:
    result = analyze_subdivision(
        _inputs(lot_width_ft=None, min_lot_width_ft=None, lot_area_sqft=5000.0)
    )
    assert result.max_lots == 3
    assert result.limiting_factor == "area"


RM1_PROVISION = small_lot_provision_for("RM-1")


def _rm1_inputs(**overrides: object) -> SubdivisionInputs:
    base: dict[str, object] = {
        "district_code": "RM-1",
        "lot_area_sqft": 1920.0,
        "lot_width_ft": 20.0,
        "min_lot_area_sqft": 1440.0,
        "min_lot_width_ft": 16.0,
        "small_lot_provision": RM1_PROVISION,
        "adjacent_small_share": 0.8,
        "has_overlay": False,
    }
    base.update(overrides)
    return SubdivisionInputs(**base)  # type: ignore[arg-type]


def test_rm1_provision_matches_the_verbatim_constants_of_14_701_2_c_1() -> None:
    assert RM1_PROVISION is not None
    assert RM1_PROVISION.trigger_lot_area_sqft == 1920.0
    assert RM1_PROVISION.min_child_lot_area_sqft == 960.0
    assert RM1_PROVISION.adjacent_small_share == 0.75
    assert RM1_PROVISION.adjacent_small_max_area_sqft == 1000.0
    assert RM1_PROVISION.min_lot_width_ft == 16.0
    assert "14-701(2)(c)[1]" in RM1_PROVISION.citation


def test_rm1_provision_splits_a_lot_the_base_minimum_would_refuse() -> None:
    result = analyze_subdivision(_rm1_inputs())

    assert result.can_subdivide
    assert result.max_lots == 2


def test_rm1_provision_does_not_reach_below_its_own_trigger() -> None:
    result = analyze_subdivision(_rm1_inputs(lot_area_sqft=1900.0))

    assert not result.can_subdivide


def test_rm1_provision_still_requires_the_adjacency_share() -> None:
    result = analyze_subdivision(_rm1_inputs(adjacent_small_share=0.5))

    assert not result.can_subdivide


def test_rsa5_citation_names_the_provision_not_the_table() -> None:
    provision = small_lot_provision_for("RSA-5")

    assert provision is not None
    assert "14-701(2)(b)[2]" in provision.citation
