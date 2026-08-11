from lotscope.zoning.buildability import DistrictStandard
from lotscope.zoning.service import _apply_overlay_modifications

BASE = DistrictStandard(
    code="RSA-5", code_version="title14-quickguide-2026-02", min_lot_area_sqft=960.0
)


def test_no_modifications_returns_the_base_standard_unchanged() -> None:
    result = _apply_overlay_modifications(BASE, [])

    assert result is BASE
    assert result.min_lot_area_sqft == 960.0
    assert result.overlay_modifications == []


def test_an_overlay_raises_the_effective_minimum_and_records_both_values() -> None:
    result = _apply_overlay_modifications(
        BASE, [("min_lot_area_sqft", 1440.0, "/EDO", "14-530(2)")]
    )

    assert result.min_lot_area_sqft == 1440.0
    assert len(result.overlay_modifications) == 1
    modification = result.overlay_modifications[0]
    assert modification.base_value == 960.0
    assert modification.value == 1440.0
    assert modification.overlay_code == "/EDO"
    assert modification.citation == "14-530(2)"


def test_two_overlays_agreeing_on_a_field_apply_once() -> None:
    result = _apply_overlay_modifications(
        BASE,
        [
            ("min_lot_area_sqft", 1440.0, "/EDO", "14-530(2)"),
            ("min_lot_area_sqft", 1440.0, "/SIX", "14-548(3)(a)(.3)"),
        ],
    )

    assert result.min_lot_area_sqft == 1440.0
    assert len(result.overlay_modifications) == 1


def test_a_disagreeing_second_overlay_is_discarded_not_silently_applied() -> None:
    result = _apply_overlay_modifications(
        BASE,
        [
            ("min_lot_area_sqft", 1440.0, "/EDO", "14-530(2)"),
            ("min_lot_area_sqft", 2000.0, "/XXX", "14-999(1)"),
        ],
    )

    assert result.min_lot_area_sqft == 1440.0
    assert len(result.overlay_modifications) == 1


def test_an_unknown_field_is_ignored_rather_than_crashing() -> None:
    result = _apply_overlay_modifications(BASE, [("not_a_field", 5.0, "/EDO", "14-530(2)")])

    assert result.overlay_modifications == []
    assert result.min_lot_area_sqft == 960.0


def test_the_base_standard_is_not_mutated() -> None:
    _apply_overlay_modifications(BASE, [("min_lot_area_sqft", 1440.0, "/EDO", "14-530(2)")])

    assert BASE.min_lot_area_sqft == 960.0
    assert BASE.overlay_modifications == []
