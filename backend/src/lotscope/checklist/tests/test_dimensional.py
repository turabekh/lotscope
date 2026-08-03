from lotscope.checklist.dimensional import (
    DimensionalContext,
    build_dimensional_items,
    deed_restriction_item,
    height_item,
    lot_area_item,
    lot_width_item,
    subdivision_item,
    unit_density_item,
    utilities_item,
    yards_item,
)

_RSA5 = DimensionalContext(
    district_code="RSA5",
    citation_label="Title 14",
    lot_area_sqft=1600.0,
    frontage_ft=16.0,
    min_lot_area_sqft=1440.0,
    min_lot_width_ft=16.0,
    max_height_ft=38.0,
    lot_area_per_unit_sqft=1440.0,
    max_occupancy_pct=75.0,
    front_setback_ft=0.0,
    rear_setback_ft=9.0,
    side_setback_ft=0.0,
    permitted_uses=("single-family",),
    by_right_units=1,
)


def test_a_conforming_lot_passes_area_and_width() -> None:
    assert lot_area_item(_RSA5).status == "pass"
    assert lot_width_item(_RSA5).status == "pass"


def test_an_undersized_lot_fails_rather_than_warning() -> None:
    undersized = DimensionalContext(**{**_RSA5.__dict__, "lot_area_sqft": 940.0})
    item = lot_area_item(undersized)

    assert item.status == "fail"
    assert "940" in item.detail
    assert "1,440" in item.detail


def test_a_missing_measurement_is_not_evaluated_rather_than_passed() -> None:
    unknown = DimensionalContext(**{**_RSA5.__dict__, "lot_area_sqft": None})
    item = lot_area_item(unknown)

    assert item.status == "not_evaluated"
    assert "not recorded" in item.detail


def test_a_missing_standard_says_so_instead_of_passing() -> None:
    bare = DimensionalContext(district_code="RSA5", lot_area_sqft=1600.0)

    assert lot_area_item(bare).status == "not_evaluated"
    assert lot_width_item(bare).status == "not_evaluated"


def test_an_unresolved_district_is_distinguished_from_a_missing_standard() -> None:
    no_district = DimensionalContext(lot_area_sqft=1600.0)

    assert "base district could not be resolved" in lot_area_item(no_district).detail


def test_a_partially_recorded_yard_set_warns_rather_than_passes() -> None:
    partial = DimensionalContext(**{**_RSA5.__dict__, "side_setback_ft": None})
    item = yards_item(partial)

    assert item.status == "potential_issue"
    assert "side" in item.detail


def test_a_lot_too_small_for_one_unit_fails_density() -> None:
    tiny = DimensionalContext(**{**_RSA5.__dict__, "lot_area_sqft": 700.0})
    item = unit_density_item(tiny)

    assert item.status == "fail"
    assert "single unit" in item.detail


def test_utilities_never_claims_service_exists() -> None:
    item = utilities_item(_RSA5)

    assert item.status == "not_evaluated"
    assert "not confirmation that service exists" in item.detail


def test_absent_deed_restrictions_are_not_a_clear_title() -> None:
    clean = DimensionalContext(**{**_RSA5.__dict__, "deed_restriction_count": 0})
    item = deed_restriction_item(clean)

    assert item.status == "not_evaluated"
    assert "not a clear-title confirmation" in item.detail


def test_found_deed_restrictions_are_flagged() -> None:
    restricted = DimensionalContext(**{**_RSA5.__dict__, "deed_restriction_count": 2})

    assert deed_restriction_item(restricted).status == "potential_issue"


def test_subdivision_is_not_applicable_on_a_small_lot() -> None:
    small = DimensionalContext(**{**_RSA5.__dict__, "subdivision_potential": False})

    assert subdivision_item(small).status == "not_applicable"


def test_every_dimensional_check_is_produced_exactly_once() -> None:
    items = build_dimensional_items(_RSA5)
    codes = [item.code for item in items]

    assert len(codes) == len(set(codes))
    assert set(codes) == {
        "permitted_use",
        "min_lot_area",
        "min_lot_width",
        "max_height",
        "floor_area",
        "yards",
        "unit_density",
        "master_plan",
        "parking",
        "utilities",
        "deed_restrictions",
        "subdivision",
    }


def test_no_dimensional_check_invents_a_pass_without_data() -> None:
    empty = DimensionalContext()

    for item in build_dimensional_items(empty):
        assert item.status in {"not_evaluated", "not_applicable"}


_CMX4 = DimensionalContext(
    district_code="CMX-4",
    citation_label="Title 14",
    lot_area_sqft=15592.0,
    frontage_ft=66.0,
    max_occupancy_pct=90.0,
    max_floor_area_ratio_pct=500.0,
    side_setback_ft=8.0,
    permitted_uses=("multi_family", "commercial"),
    standard_loaded=True,
)


def test_a_loaded_standard_is_never_reported_as_missing() -> None:
    details = [item.detail for item in build_dimensional_items(_CMX4)]

    assert not any("No zoning standard is loaded" in detail for detail in details)


def test_an_unrecorded_field_names_the_district_and_the_field() -> None:
    detail = height_item(_CMX4).detail

    assert detail == (
        "The CMX-4 standard on file records no maximum height, so this check was not evaluated."
    )


def test_a_district_with_no_standard_says_so() -> None:
    context = DimensionalContext(district_code="CMX-4", standard_loaded=False)

    assert height_item(context).detail == (
        "No zoning standard is loaded for CMX-4, so this check was not evaluated."
    )


def test_every_check_carries_a_distinct_label() -> None:
    labels = [item.label for item in build_dimensional_items(_CMX4)]

    assert len(labels) == len(set(labels))
    assert all(label for label in labels)


_CMX4_WITH_DISPOSITIONS = DimensionalContext(
    **{
        **_CMX4.__dict__,
        "field_dispositions": {
            "min_lot_area_sqft": {"disposition": "unregulated"},
            "max_height_ft": {
                "disposition": "unregulated",
                "note": "building size is governed by the floor-area ratio",
            },
        },
    }
)


def test_an_unregulated_standard_is_answered_not_left_unevaluated() -> None:
    item = lot_area_item(_CMX4_WITH_DISPOSITIONS)

    assert item.status == "not_applicable"
    assert item.detail == "CMX-4 sets no minimum lot area."


def test_an_unregulated_standard_can_say_what_governs_instead() -> None:
    item = height_item(_CMX4_WITH_DISPOSITIONS)

    assert item.status == "not_applicable"
    assert item.detail == (
        "CMX-4 sets no maximum height — building size is governed by the floor-area ratio."
    )


def test_a_conditional_standard_says_why_it_cannot_be_reduced_to_a_figure() -> None:
    context = DimensionalContext(
        district_code="I-1",
        standard_loaded=True,
        field_dispositions={
            "max_height_ft": {
                "disposition": "conditional",
                "note": "60 ft. where the lot abuts a Residential district; otherwise no limit",
            }
        },
    )
    item = height_item(context)

    assert item.status == "not_evaluated"
    assert "60 ft. where the lot abuts a Residential district" in item.detail
    assert "not modelled" in item.detail


def test_a_field_with_no_disposition_still_reports_as_uncaptured() -> None:
    item = height_item(_CMX4)

    assert item.status == "not_evaluated"
    assert "standard on file records no maximum height" in item.detail
