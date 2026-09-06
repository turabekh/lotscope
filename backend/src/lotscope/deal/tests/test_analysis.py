from lotscope.deal.analysis import DealAnalysis, DealAssumptions, DealInputs, analyze_deal

ASSUMPTIONS = DealAssumptions(
    construction_cost_per_sqft=175.0,
    soft_cost_pct=0.15,
    selling_cost_pct=0.07,
    target_margin=0.20,
    default_unit_sqft=1200.0,
    max_unit_sqft=3000.0,
)


def _inputs(**overrides: object) -> DealInputs:
    base: dict[str, object] = {
        "units": 3,
        "buildable_area_sqft": 1000.0,
        "estimated_floors": 3,
        "finished_comp_prices": [300_000.0, 320_000.0, 310_000.0, 305_000.0, 315_000.0],
        "land_value": 120_000.0,
        "acquisition_price": None,
    }
    base.update(overrides)
    return DealInputs(**base)  # type: ignore[arg-type]


def test_arv_is_per_unit_median_times_units() -> None:
    result = analyze_deal(_inputs(), ASSUMPTIONS)
    assert result.per_unit_value == 310_000.0
    assert result.arv == 930_000.0


def test_gross_floor_area_uses_envelope_when_available() -> None:
    result = analyze_deal(_inputs(), ASSUMPTIONS)
    assert result.gross_floor_area_sqft == 3000.0
    assert result.construction_cost == 525_000.0


def test_gross_floor_area_falls_back_to_default_unit_size() -> None:
    result = analyze_deal(_inputs(buildable_area_sqft=None, estimated_floors=None), ASSUMPTIONS)
    assert result.gross_floor_area_sqft == 3600.0


def test_oversized_envelope_is_capped_by_unit_count() -> None:
    result = analyze_deal(
        _inputs(units=1, buildable_area_sqft=37449.0, estimated_floors=3), ASSUMPTIONS
    )
    assert result.gross_floor_area_sqft == 3000.0
    assert result.construction_cost == 525000.0
    assert any("capped" in reason for reason in result.reasons)


def test_normal_envelope_is_not_capped() -> None:
    result = analyze_deal(
        _inputs(units=2, buildable_area_sqft=1000.0, estimated_floors=3), ASSUMPTIONS
    )
    assert result.gross_floor_area_sqft == 3000.0
    assert not any("capped" in reason for reason in result.reasons)


def test_feasibility_identity_holds() -> None:
    result = analyze_deal(_inputs(acquisition_price=120_000.0), ASSUMPTIONS)
    components = [
        result.acquisition_cost,
        result.construction_cost,
        result.soft_cost,
        result.selling_cost,
        result.total_cost,
        result.profit,
        result.arv,
    ]
    assert all(value is not None for value in components)
    assert result.total_cost == (
        result.acquisition_cost  # type: ignore[operator]
        + result.construction_cost
        + result.soft_cost
        + result.selling_cost
    )
    assert result.profit == result.arv - result.total_cost  # type: ignore[operator]


def test_offering_the_max_allowable_offer_hits_the_target_margin() -> None:
    base = analyze_deal(_inputs(), ASSUMPTIONS)
    assert base.max_allowable_offer is not None
    at_mao = analyze_deal(_inputs(acquisition_price=base.max_allowable_offer), ASSUMPTIONS)
    assert at_mao.margin is not None
    assert abs(at_mao.margin - ASSUMPTIONS.target_margin) < 0.005
    assert at_mao.is_underpriced is True


def test_overpaying_above_mao_is_not_underpriced() -> None:
    base = analyze_deal(_inputs(), ASSUMPTIONS)
    assert base.max_allowable_offer is not None
    over = analyze_deal(_inputs(acquisition_price=base.max_allowable_offer + 50_000), ASSUMPTIONS)
    assert over.is_underpriced is False
    assert over.margin is not None
    assert over.margin < ASSUMPTIONS.target_margin


def test_acquisition_defaults_to_land_value() -> None:
    result = analyze_deal(_inputs(acquisition_price=None, land_value=120_000.0), ASSUMPTIONS)
    assert result.acquisition_cost == 120_000.0


def test_deal_score_scales_with_margin() -> None:
    base = analyze_deal(_inputs(), ASSUMPTIONS)
    assert base.max_allowable_offer is not None
    at_target = analyze_deal(_inputs(acquisition_price=base.max_allowable_offer), ASSUMPTIONS)
    cheaper = analyze_deal(
        _inputs(acquisition_price=base.max_allowable_offer - 100_000), ASSUMPTIONS
    )
    assert at_target.deal_score is not None
    assert cheaper.deal_score is not None
    assert 0.0 <= at_target.deal_score <= 100.0
    assert cheaper.deal_score > at_target.deal_score


def test_feasible_build_is_not_infeasible() -> None:
    result = analyze_deal(_inputs(), ASSUMPTIONS)
    assert result.infeasible is False
    assert result.max_allowable_offer is not None
    assert result.max_allowable_offer > 0


def test_infeasible_build_floors_mao_at_zero_and_flags() -> None:
    result = analyze_deal(
        _inputs(
            units=1,
            buildable_area_sqft=1557.0,
            estimated_floors=3,
            finished_comp_prices=[97_500.0, 95_000.0, 99_000.0],
            land_value=22_000.0,
            acquisition_price=None,
        ),
        ASSUMPTIONS,
    )
    assert result.infeasible is True
    assert result.max_allowable_offer == 0.0
    assert result.arv == 97_500.0
    assert result.construction_cost is not None
    assert result.construction_cost > result.arv
    assert any("land price of $0" in reason for reason in result.reasons)


def test_infeasible_build_is_never_underpriced() -> None:
    result = analyze_deal(
        _inputs(
            units=1,
            buildable_area_sqft=1557.0,
            estimated_floors=3,
            finished_comp_prices=[97_500.0, 95_000.0, 99_000.0],
            land_value=None,
            acquisition_price=1.0,
        ),
        ASSUMPTIONS,
    )
    assert result.infeasible is True
    assert result.max_allowable_offer == 0.0
    assert result.is_underpriced is False


def test_no_units_returns_unknown() -> None:
    result = analyze_deal(_inputs(units=None), ASSUMPTIONS)
    assert isinstance(result, DealAnalysis)
    assert result.arv is None
    assert result.confidence == "low"
    assert result.reasons


def test_no_finished_comps_returns_unknown() -> None:
    result = analyze_deal(_inputs(finished_comp_prices=[]), ASSUMPTIONS)
    assert result.arv is None
    assert result.max_allowable_offer is None


def test_missing_acquisition_and_land_value_still_reports_mao() -> None:
    result = analyze_deal(_inputs(acquisition_price=None, land_value=None), ASSUMPTIONS)
    assert result.max_allowable_offer is not None
    assert result.acquisition_cost is None
    assert result.profit is None
    assert result.is_underpriced is None


def test_confidence_degrades_with_thin_comps() -> None:
    thin = analyze_deal(_inputs(finished_comp_prices=[300_000.0, 700_000.0]), ASSUMPTIONS)
    assert thin.confidence == "low"


def test_an_assessed_fallback_is_not_called_a_modelled_value() -> None:
    assessed = analyze_deal(
        DealInputs(
            units=4,
            buildable_area_sqft=1342,
            estimated_floors=3,
            finished_comp_prices=[880000.0, 890000.0, 875000.0],
            land_value=527800.0,
            acquisition_price=None,
            land_value_is_assessed=True,
        ),
        ASSUMPTIONS,
    )
    reason = " ".join(assessed.reasons)
    assert "assessed value" in reason
    assert "no comparable land sales were available" in reason
    assert "AVM" not in reason

    modelled = analyze_deal(
        DealInputs(
            units=4,
            buildable_area_sqft=1342,
            estimated_floors=3,
            finished_comp_prices=[880000.0, 890000.0, 875000.0],
            land_value=527800.0,
            acquisition_price=None,
            land_value_is_assessed=False,
        ),
        ASSUMPTIONS,
    )
    assert "modelled land value" in " ".join(modelled.reasons)


def _at_margin(margin: float) -> DealAnalysis:
    return analyze_deal(
        _inputs(),
        DealAssumptions(
            construction_cost_per_sqft=175.0,
            soft_cost_pct=0.15,
            selling_cost_pct=0.07,
            target_margin=margin,
            default_unit_sqft=1200.0,
            max_unit_sqft=3000.0,
        ),
    )


def test_a_stricter_margin_lowers_what_the_lot_is_worth_paying() -> None:
    """The offer is computed from the margin, so changing one has to move the other.

    This lives here rather than in a browser test: whether the figure moves on screen for
    a given fixture depends on that fixture being feasible, and the e2e seed is not. The
    arithmetic is the thing being claimed, and it is the same everywhere.
    """
    permissive = _at_margin(0.20).max_allowable_offer
    strict = _at_margin(0.35).max_allowable_offer

    assert permissive is not None
    assert strict is not None
    assert permissive > strict


def test_the_offer_moves_monotonically_as_the_margin_rises() -> None:
    offers = [_at_margin(margin).max_allowable_offer for margin in (0.10, 0.20, 0.30, 0.40)]
    assert all(offer is not None for offer in offers)
    figures = [offer for offer in offers if offer is not None]
    assert figures == sorted(figures, reverse=True)
