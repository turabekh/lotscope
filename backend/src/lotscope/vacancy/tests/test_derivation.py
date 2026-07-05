from lotscope.vacancy.derivation import (
    DERIVED_MULTI_SIGNAL,
    DERIVED_SINGLE_SIGNAL,
    derive_vacancy,
)


def test_vacant_land_with_zero_improvement_is_multi_signal() -> None:
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 0.0) == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("COMMERCIAL LAND", 500.0) == (True, DERIVED_MULTI_SIGNAL)


def test_vacant_land_use_only_is_single_signal_when_improvement_unknown() -> None:
    assert derive_vacancy("UNBUILDABLE LOT", None) == (True, DERIVED_SINGLE_SIGNAL)


def test_vacant_land_use_with_real_structure_is_not_vacant() -> None:
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 45000.0) == (False, None)


def test_non_vacant_use_is_not_vacant() -> None:
    assert derive_vacancy("PARKING LOT/GARAGE", 0.0) == (False, None)
    assert derive_vacancy("2 STORY RESIDENCE", 0.0) == (False, None)
    assert derive_vacancy(None, 0.0) == (False, None)


def test_confidence_ordering_model_gt_multi_gt_single() -> None:
    # VPI model baseline (0.6) > multi-signal derived > single-signal derived
    assert 0.6 > DERIVED_MULTI_SIGNAL > DERIVED_SINGLE_SIGNAL
