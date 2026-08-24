from lotscope.vacancy.derivation import (
    DERIVED_MULTI_SIGNAL,
    DERIVED_SINGLE_SIGNAL,
    derive_vacancy,
)


def test_vacant_land_with_zero_improvement_is_multi_signal() -> None:
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 0.0, "hbg") == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("COMMERCIAL LAND", 500.0, "hbg") == (True, DERIVED_MULTI_SIGNAL)


def test_vacant_land_use_only_is_single_signal_when_improvement_unknown() -> None:
    assert derive_vacancy("UNBUILDABLE LOT", None, "hbg") == (True, DERIVED_SINGLE_SIGNAL)


def test_vacant_land_use_with_real_structure_is_not_vacant() -> None:
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 45000.0, "hbg") == (False, None)


def test_non_vacant_use_is_not_vacant() -> None:
    assert derive_vacancy("PARKING LOT/GARAGE", 0.0, "hbg") == (False, None)
    assert derive_vacancy("2 STORY RESIDENCE", 0.0, "hbg") == (False, None)
    assert derive_vacancy(None, 0.0, "hbg") == (False, None)


def test_pgh_vacant_land_uses_are_vacant() -> None:
    assert derive_vacancy("VACANT LAND", 0.0, "pgh") == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT COMMERCIAL LAND", 500.0, "pgh") == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT INDUSTRIAL LAND", None, "pgh") == (True, DERIVED_SINGLE_SIGNAL)
    assert derive_vacancy(">10 ACRES VACANT", 0.0, "pgh") == (True, DERIVED_MULTI_SIGNAL)


def test_pgh_vacant_use_with_structure_is_not_vacant() -> None:
    assert derive_vacancy("VACANT LAND", 45000.0, "pgh") == (False, None)


def test_pgh_built_use_is_not_vacant() -> None:
    assert derive_vacancy("SINGLE FAMILY", 0.0, "pgh") == (False, None)
    assert derive_vacancy("ROWHOUSE", 0.0, "pgh") == (False, None)


def test_vocabulary_is_market_scoped() -> None:
    assert derive_vacancy("VACANT LAND", 0.0, "hbg") == (False, None)
    assert derive_vacancy("BLDG LOT UNDER 1 ACRE", 0.0, "pgh") == (False, None)
    assert derive_vacancy("VACANT LAND", 0.0, "unknown_market") == (False, None)


def test_confidence_ordering_model_gt_multi_gt_single() -> None:
    assert 0.6 > DERIVED_MULTI_SIGNAL > DERIVED_SINGLE_SIGNAL


def test_phl_vacant_land_uses_are_vacant() -> None:
    assert derive_vacancy("VACANT LAND", 0.0, "phl") == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT LAND - RESIDENTIAL", 0.0, "phl") == (True, DERIVED_MULTI_SIGNAL)
    assert derive_vacancy("VACANT LAND - NON-RESIDENTIAL", 500.0, "phl") == (
        True,
        DERIVED_MULTI_SIGNAL,
    )


def test_phl_vacant_use_with_structure_is_not_vacant() -> None:
    assert derive_vacancy("VACANT LAND", 45000.0, "phl") == (False, None)


def test_phl_built_use_is_not_vacant() -> None:
    assert derive_vacancy("ROW B/GAR 2 STY MASONRY", 0.0, "phl") == (False, None)
    assert derive_vacancy("APARTMENTS  > 4 UNITS", 0.0, "phl") == (False, None)
