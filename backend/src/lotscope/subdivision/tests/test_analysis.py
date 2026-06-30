from lotscope.subdivision.analysis import SubdivisionInputs, analyze_subdivision


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
