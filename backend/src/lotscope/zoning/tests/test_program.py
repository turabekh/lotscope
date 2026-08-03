from lotscope.zoning.program import ProgramInputs, compose_development_program

_CMX4 = ProgramInputs(
    district_code="CMX-4",
    cited_section="CMX-4 (Title 14, title14-quickguide-2026-02)",
    lot_area_sqft=15592.0,
    permitted_uses=("multi_family", "commercial"),
    can_build_by_right=True,
    needs_variance=False,
    by_right_units=70,
    unit_basis="far_estimate",
    max_height_ft=None,
    height_unregulated=True,
    max_floor_area_ratio_pct=500.0,
    max_occupancy_pct=90.0,
    buildable_area_sqft=14032.8,
    footprint_basis="coverage_estimate",
    confidence="high",
    outstanding_checks=("Parking & loading", "Utility service"),
)

_RSA5 = ProgramInputs(
    district_code="RSA-5",
    cited_section="RSA-5 (Title 14, title14-quickguide-2026-02)",
    lot_area_sqft=1600.0,
    permitted_uses=("single_family",),
    can_build_by_right=True,
    needs_variance=False,
    by_right_units=1,
    unit_basis="flat_cap",
    max_height_ft=38.0,
    buildable_area_sqft=1458.0,
    footprint_basis="setback_calculated",
    confidence="high",
)


def test_the_statement_answers_what_can_be_built_in_plain_language() -> None:
    program = compose_development_program(_RSA5)

    assert "On this 1,600 sq ft RSA-5 lot, single-family uses are permitted by right." in (
        program.statement
    )
    assert "caps height at 38 ft" in program.statement
    assert "buildable footprint calculates to about 1,458 sq ft" in program.statement


def test_the_statement_cites_the_standard_and_its_version() -> None:
    program = compose_development_program(_RSA5)

    assert program.citation == "RSA-5 (Title 14, title14-quickguide-2026-02)"


def test_an_unregulated_height_says_what_governs_bulk_instead() -> None:
    statement = compose_development_program(_CMX4).statement

    assert "CMX-4 sets no maximum height" in statement
    assert "500% floor-area ratio" in statement
    assert "90% lot-coverage limit" in statement


def test_a_coverage_estimated_footprint_is_marked_indicative() -> None:
    statement = compose_development_program(_CMX4).statement

    assert "from lot coverage rather than measured setbacks" in statement
    assert "indicative" in statement


def test_claims_separate_verified_facts_from_calculated_and_estimated_ones() -> None:
    states = {claim.label: claim.state for claim in compose_development_program(_CMX4).claims}

    assert states["Base district"] == "verified"
    assert states["Lot area"] == "verified"
    assert states["Maximum height"] == "verified"
    assert states["By-right units"] == "estimated"
    assert states["Buildable footprint"] == "estimated"


def test_a_setback_derived_footprint_is_calculated_not_estimated() -> None:
    states = {claim.label: claim.state for claim in compose_development_program(_RSA5).claims}

    assert states["Buildable footprint"] == "calculated"
    assert states["Maximum height"] == "calculated"


def test_an_unrecorded_height_is_unavailable_not_unregulated() -> None:
    inputs = ProgramInputs(**{**_RSA5.__dict__, "max_height_ft": None})
    states = {claim.label: claim.state for claim in compose_development_program(inputs).claims}

    assert states["Maximum height"] == "unavailable"
    assert "vertical envelope is unverified" in compose_development_program(inputs).statement


def test_outstanding_checks_force_conditional_language() -> None:
    conditions = compose_development_program(_CMX4).conditions

    assert any("Still unevaluated: Parking & loading and Utility service." in c for c in conditions)
    assert any("reads the base district only" in c for c in conditions)


def test_every_program_carries_the_informational_disclaimer() -> None:
    for inputs in (_CMX4, _RSA5, ProgramInputs()):
        conditions = compose_development_program(inputs).conditions
        assert any("not a zoning determination" in c for c in conditions)


def test_a_variance_case_is_not_described_as_by_right() -> None:
    inputs = ProgramInputs(
        **{**_RSA5.__dict__, "can_build_by_right": False, "needs_variance": True}
    )
    statement = compose_development_program(inputs).statement

    assert "permitted by right" not in statement
    assert "variance or special exception is likely required" in statement
    assert "Were a variance granted" in statement
    assert "before other limits apply" not in statement

    labels = [claim.label for claim in compose_development_program(inputs).claims]
    assert "By-right units" not in labels
    assert "Units if a variance is granted" in labels


def test_a_master_plan_district_is_stated_prominently_and_first() -> None:
    inputs = ProgramInputs(
        **{**_RSA5.__dict__, "district_code": "SP-INS", "requires_master_plan": True}
    )
    program = compose_development_program(inputs)

    assert program.statement.startswith("On this 1,600 sq ft SP-INS lot, development is not ")
    assert "approved master plan" in program.statement
    assert not any(
        claim.label == "By-right units" and claim.state != "unavailable" for claim in program.claims
    )


def test_an_unresolved_district_describes_no_program_at_all() -> None:
    program = compose_development_program(ProgramInputs())

    assert program.statement == (
        "The base zoning district could not be resolved for this parcel, so no development "
        "program can be described."
    )
    assert program.claims == ()
    assert program.citation is None


def test_low_confidence_is_stated_rather_than_left_implicit() -> None:
    inputs = ProgramInputs(**{**_CMX4.__dict__, "confidence": "medium"})

    assert any(
        "Confidence in this read is medium" in c
        for c in compose_development_program(inputs).conditions
    )


def test_flagged_checks_warn_that_the_figures_may_change() -> None:
    inputs = ProgramInputs(**{**_RSA5.__dict__, "flagged_checks": ("Required yards",)})
    conditions = compose_development_program(inputs).conditions

    assert any("Flagged for a closer look: Required yards." in c for c in conditions)
    assert any("figures above may change" in c for c in conditions)
