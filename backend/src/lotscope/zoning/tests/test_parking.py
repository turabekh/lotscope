import pytest

from lotscope.zoning.parking import (
    ParkingRequirement,
    parking_requirement,
    required_spaces,
    requirement_phrase,
)


@pytest.mark.parametrize(
    ("district", "use", "spaces", "per_units"),
    [
        ("RSA-5", "single_family", 0, 1),
        ("RSA-4", "single_family", 0, 1),
        ("RM-1", "multi_family", 0, 1),
        ("RSD-3", "single_family", 1, 1),
        ("RSA-1", "single_family", 1, 1),
        ("RMX-1", "multi_family", 1, 1),
        ("RM-2", "single_family", 0, 1),
        ("RM-3", "two_family", 1, 2),
        ("RM-4", "multi_family", 3, 10),
        ("CMX-2", "multi_family", 0, 1),
        ("CMX-2.5", "multi_family", 0, 1),
        ("CMX-3", "multi_family", 3, 10),
        ("CMX-4", "multi_family", 0, 1),
        ("CMX-5", "multi_family", 0, 1),
        ("IRMX", "multi_family", 3, 10),
        ("ICMX", "multi_family", 1, 2),
    ],
)
def test_chapter_14_800_ratios(district: str, use: str, spaces: int, per_units: int) -> None:
    requirement = parking_requirement(district, use)
    assert requirement is not None
    assert (requirement.spaces, requirement.per_units) == (spaces, per_units)


def test_the_most_common_philadelphia_district_requires_none() -> None:
    requirement = parking_requirement("RSA-5", "single_family")
    assert requirement is not None
    assert requirement.spaces == 0
    assert requirement_phrase(requirement) == "no off-street parking"


def test_districts_governed_by_their_own_section_are_not_modelled() -> None:
    for district in ("CMX-1", "CA-1", "CA-2"):
        assert parking_requirement(district, "multi_family") is None


def test_an_unknown_district_is_not_guessed() -> None:
    assert parking_requirement("ZZ-9", "multi_family") is None


def test_a_hyphenless_parcel_code_still_resolves() -> None:
    assert parking_requirement("RSA5", "single_family") == parking_requirement(
        "RSA-5", "single_family"
    )


def test_phrases_read_as_the_code_states_them() -> None:
    assert requirement_phrase(ParkingRequirement(0, 1, "t")) == "no off-street parking"
    assert (
        requirement_phrase(ParkingRequirement(1, 1, "t")) == "1 off-street space per dwelling unit"
    )
    assert (
        requirement_phrase(ParkingRequirement(1, 2, "t"))
        == "1 off-street space per 2 dwelling units"
    )
    assert (
        requirement_phrase(ParkingRequirement(3, 10, "t"))
        == "3 off-street spaces per 10 dwelling units"
    )


def test_a_space_count_is_given_only_when_the_ratio_divides_exactly() -> None:
    assert required_spaces(ParkingRequirement(3, 10, "t"), 10) == 3
    assert required_spaces(ParkingRequirement(1, 2, "t"), 4) == 2
    assert required_spaces(ParkingRequirement(1, 1, "t"), 3) == 3
    assert required_spaces(ParkingRequirement(0, 1, "t"), 7) == 0


def test_no_rounding_rule_is_invented_for_a_partial_space() -> None:
    assert required_spaces(ParkingRequirement(3, 10, "t"), 4) is None
    assert required_spaces(ParkingRequirement(1, 2, "t"), 3) is None


def test_every_requirement_names_the_table_it_came_from() -> None:
    for district, table in (
        ("RSA-5", "Table 14-802-1"),
        ("CMX-4", "Table 14-802-2"),
        ("IRMX", "Table 14-802-3"),
    ):
        requirement = parking_requirement(district, "multi_family")
        assert requirement is not None
        assert requirement.table == table
