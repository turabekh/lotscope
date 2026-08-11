import pytest

from lotscope.zoning.verify import (
    TABLE_14_701_1_MIN_LOT_AREA,
    Divergence,
    _check_printed_table,
    _numerals,
)


def test_a_matching_seed_reports_no_divergence() -> None:
    assert _check_printed_table("t1", "min_lot_area_sqft", TABLE_14_701_1_MIN_LOT_AREA) == []


def test_a_diverging_value_is_caught() -> None:
    printed: dict[str, float] = {**TABLE_14_701_1_MIN_LOT_AREA, "RSA-5": 1440}

    divergences = _check_printed_table("t1", "min_lot_area_sqft", printed)

    assert len(divergences) == 1
    assert divergences[0].subject == "RSA-5"
    assert divergences[0].expected == "1440"
    assert divergences[0].actual == "960"


def test_the_check_is_value_based_not_version_based() -> None:
    printed: dict[str, float] = {"RSA-5": 1440}

    assert _check_printed_table("t1", "min_lot_area_sqft", printed) != []


def test_a_field_absent_from_the_seed_is_caught() -> None:
    divergences = _check_printed_table("t4", "max_floor_area_ratio_pct", {"I-P": 500})

    assert len(divergences) == 1
    assert divergences[0].actual == "absent from seed"


@pytest.mark.parametrize(
    ("body", "wanted"),
    [("minimum lot area shall be 1,440 sq. ft.", "1440"), ("at least 1,600 sq. ft.", "1600")],
)
def test_numerals_strip_thousands_separators(body: str, wanted: str) -> None:
    assert wanted in _numerals(body)


def test_divergence_carries_enough_to_locate_the_defect() -> None:
    divergence = Divergence("table-14-701-1", "RSA-5", "min_lot_area_sqft", "960", "1440")

    assert divergence.scope == "table-14-701-1"
    assert divergence.subject == "RSA-5"
    assert divergence.field == "min_lot_area_sqft"
