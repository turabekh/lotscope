def test_assumptions_source_requires_explicit_calibration_marker() -> None:
    from lotscope.deal.service import assumptions_source

    assert assumptions_source({}) == "market_default"
    # a seeded market-specific default value is NOT reviewer-calibrated
    assert assumptions_source({"deal_construction_cost_per_sqft": 145.0}) == "market_default"
    assert assumptions_source(None) == "market_default"
    # only an explicit marker reads calibrated
    assert (
        assumptions_source({"deal_construction_cost_per_sqft": 145.0, "calibrated": True})
        == "calibrated"
    )
