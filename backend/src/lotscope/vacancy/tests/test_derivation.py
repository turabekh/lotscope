from lotscope.vacancy.derivation import (
    DERIVED_MULTI_SIGNAL,
    DERIVED_SINGLE_SIGNAL,
    derive_vacancy,
)


def test_vacant_land_with_zero_improvement_is_multi_signal() -> None:
    assert derive_vacancy("VACANT LAND", 0.0) == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT LAND - RESIDENTIAL", 500.0) == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT LAND - NON-RESIDENTIAL", 500.0) == (True, DERIVED_MULTI_SIGNAL)


def test_vacant_land_use_only_is_single_signal_when_improvement_unknown() -> None:
    assert derive_vacancy("VACANT LAND", None) == (True, DERIVED_SINGLE_SIGNAL)


def test_vacant_land_use_with_real_structure_is_not_vacant() -> None:
    assert derive_vacancy("VACANT LAND", 45000.0) == (False, None)


def test_non_vacant_use_is_not_vacant() -> None:
    assert derive_vacancy("ROW B/GAR 2 STY MASONRY", 0.0) == (False, None)
    assert derive_vacancy("APARTMENTS  > 4 UNITS", 0.0) == (False, None)
    assert derive_vacancy(None, 0.0) == (False, None)


def test_a_use_outside_the_philadelphia_vocabulary_is_not_vacant() -> None:
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 0.0) == (False, None)
    assert derive_vacancy("VACANT COMMERCIAL LAND", 0.0) == (False, None)


def test_confidence_ordering_model_gt_multi_gt_single() -> None:
    assert 0.6 > DERIVED_MULTI_SIGNAL > DERIVED_SINGLE_SIGNAL
