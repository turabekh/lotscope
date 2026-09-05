from datetime import UTC, date, datetime

from lotscope.buybox.schemas import DEFAULT_FLIP_BID_RATIO, BuyBoxRead, BuyBoxWrite
from lotscope.packet.compose import LotInputs, compose_packet, decide, is_scheduled, red_flags
from lotscope.packet.schemas import AdjacentParcel, DataAsOf, PacketComp, PacketModel

SALE_DATE = date(2026, 9, 16)
TODAY = date(2026, 9, 5)
GENERATED_AT = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
REQUIRED_MARGIN = 0.20


def _buy_box(**overrides: object) -> BuyBoxRead:
    written = BuyBoxWrite(**overrides)
    return BuyBoxRead.model_validate(
        {
            **written.model_dump(),
            "user_id": 1,
            "is_configured": True,
            "created_at": GENERATED_AT,
            "updated_at": GENERATED_AT,
        }
    )


def _lot(**overrides: object) -> LotInputs:
    base: dict[str, object] = {
        "parcel_number": "phl:1",
        "address": "1 TEST ST",
        "case_number": "2609-001",
        "sale_type": "Tax",
        "sale_date": SALE_DATE,
        "opening_bid": 8_000.0,
        "status": "Scheduled - Tax",
        "is_vacant": True,
        "lot_area_sqft": 1_200.0,
        "zoning_code": "RSA-5",
        "can_build_by_right": True,
        "by_right_units": 1,
        "max_allowable_offer": 60_000.0,
        "est_margin": 0.28,
    }
    base.update(overrides)
    return LotInputs(**base)  # type: ignore[arg-type]


def _compose(lots: list[LotInputs], buy_box: BuyBoxRead | None = None) -> PacketModel:
    return compose_packet(
        sale_date=SALE_DATE,
        buy_box=buy_box or _buy_box(),
        required_margin=REQUIRED_MARGIN,
        lots=lots,
        data_as_of=[DataAsOf(source="opa_properties_public", source_url="https://example.test")],
        generated_at=GENERATED_AT,
        today=TODAY,
    )


def test_a_postponed_sale_with_a_future_date_is_still_scheduled() -> None:
    assert is_scheduled("Postponed", SALE_DATE, TODAY) is True
    assert is_scheduled("Scheduled - Tax", SALE_DATE, TODAY) is True
    assert is_scheduled("Sold", SALE_DATE, TODAY) is False
    assert is_scheduled("Withdrawn", SALE_DATE, TODAY) is False
    assert is_scheduled("Postponed", date(2026, 1, 1), TODAY) is False


def test_a_clean_lot_inside_the_buy_box_is_a_bid() -> None:
    verdict, reason, _rule, _also = decide(_lot(), _buy_box(max_bid=95_000), REQUIRED_MARGIN)

    assert verdict == "BID"
    assert "$60,000" in reason
    assert "28.0%" in reason


def test_an_offer_above_the_ceiling_is_a_pass() -> None:
    verdict, reason, _rule, _also = decide(
        _lot(max_allowable_offer=150_000.0), _buy_box(max_bid=95_000), REQUIRED_MARGIN
    )

    assert verdict == "PASS"
    assert "$95,000 ceiling" in reason


def test_an_opening_bid_above_what_the_lot_supports_is_a_look_not_a_pass() -> None:
    verdict, reason, rule, _also = decide(_lot(opening_bid=90_000.0), _buy_box(), REQUIRED_MARGIN)

    assert verdict == "LOOK"
    assert "under the $90,000 opening bid" in reason
    assert rule == "build: by-right eligible, MAO below opening bid"


def test_a_margin_under_the_target_is_a_pass_with_the_rule_named() -> None:
    verdict, reason, rule, _also = decide(_lot(est_margin=0.17), _buy_box(), REQUIRED_MARGIN)

    assert verdict == "PASS"
    assert "17.0% margin is under your 20.0% target" in reason
    assert rule == "build: by-right eligible, margin under target"


def test_a_tax_delinquency_is_a_flag_but_does_not_change_the_grade() -> None:
    clean, _, clean_rule, _also = decide(_lot(), _buy_box(), REQUIRED_MARGIN)
    owing, _, owing_rule, _also2 = decide(
        _lot(is_delinquent=True, total_due=9_000.0), _buy_box(), REQUIRED_MARGIN
    )

    assert clean == owing == "BID"
    assert clean_rule == owing_rule
    assert any(flag.code == "tax_delinquent" for flag in red_flags(_lot(is_delinquent=True)))


def test_a_blocking_red_flag_passes_the_lot_under_every_lens() -> None:
    for use in ("build", "assemble", "flip"):
        verdict, reason, rule, also = decide(
            _lot(has_unsafe_structure=True), _buy_box(target_use=use), REQUIRED_MARGIN
        )
        assert verdict == "PASS", use
        assert "unsafe or imminently dangerous" in reason
        assert rule == "all lenses: blocking red flag"
        assert also == []


def test_an_excluded_hazard_blocks_every_lens_too() -> None:
    flood, _, rule, _also = decide(
        _lot(in_flood_zone=True), _buy_box(target_use="flip", exclude_flood=True), REQUIRED_MARGIN
    )
    historic, _, _r, _a = decide(
        _lot(in_historic_district=True),
        _buy_box(target_use="assemble", exclude_historic=True),
        REQUIRED_MARGIN,
    )

    assert flood == historic == "PASS"
    assert rule == "all lenses: blocking red flag"


def test_no_computable_offer_is_a_look_not_a_silent_pass() -> None:
    verdict, reason, rule, _also = decide(
        _lot(max_allowable_offer=None, est_margin=None), _buy_box(), REQUIRED_MARGIN
    )

    assert verdict == "LOOK"
    assert "no offer could be computed" in reason.lower()
    assert rule == "build: by-right eligible, offer not computable"


def test_nothing_buildable_by_right_is_a_pass_when_the_zba_outlook_is_poor() -> None:
    verdict, reason, rule, _also = decide(
        _lot(
            can_build_by_right=False,
            variance_needed="Lot area 602 sqft is below the 1440 sqft minimum for RSA5.",
            variance_outlook_favourable=False,
            variance_outlook_basis="18% of 44 decided appeals granted over 36 months for RSA5",
        ),
        _buy_box(),
        REQUIRED_MARGIN,
    )

    assert verdict == "PASS"
    assert "602 sqft is below the 1440 sqft minimum" in reason
    assert "18% of 44 decided appeals" in reason
    assert rule == "build: variance needed, ZBA outlook not favourable"


def test_a_favourable_zba_outlook_turns_a_variance_lot_into_a_look() -> None:
    verdict, reason, rule, _also = decide(
        _lot(
            can_build_by_right=False,
            variance_needed="Lot width 14 ft is below the 16 ft minimum for RSA5.",
            variance_outlook_favourable=True,
            variance_outlook_basis="71% of 52 decided appeals granted over 36 months for RSA5",
        ),
        _buy_box(),
        REQUIRED_MARGIN,
    )

    assert verdict == "LOOK"
    assert "Lot width 14 ft is below the 16 ft minimum" in reason
    assert "71% of 52 decided appeals" in reason
    assert rule == "build: variance needed, ZBA outlook favourable"


def test_each_buy_box_exclusion_passes_the_lot_with_its_own_reason() -> None:
    cases: list[tuple[dict[str, object], dict[str, object], str]] = [
        ({"in_historic_district": True}, {"exclude_historic": True}, "historic district"),
        ({"in_flood_zone": True}, {"exclude_flood": True}, "flood hazard area"),
        ({"open_violation_count": 3}, {"exclude_open_violations": True}, "open l&i violations"),
        ({"city_neighbor": True}, {"exclude_city_neighbor": True}, "publicly held neighbour"),
        ({"lot_area_sqft": 400.0}, {"min_lot_sqft": 640}, "below your 640 sqft floor"),
        ({"zoning_code": "I-2"}, {"zoning_codes": ["RSA-5"]}, "not one of your districts"),
    ]
    for lot_kwargs, box_kwargs, expected in cases:
        verdict, reason, _rule, _also = decide(
            _lot(**lot_kwargs), _buy_box(**box_kwargs), REQUIRED_MARGIN
        )
        assert verdict == "PASS", (lot_kwargs, reason)
        assert expected in reason.lower(), (lot_kwargs, reason)


def test_a_hyphenated_buy_box_code_matches_the_hyphenless_one_the_city_stores() -> None:
    verdict, _, _rule, _also = decide(
        _lot(zoning_code="RSA5"), _buy_box(zoning_codes=["RSA-5"]), REQUIRED_MARGIN
    )
    reversed_verdict, _, _rule, _also = decide(
        _lot(zoning_code="RSA-5"), _buy_box(zoning_codes=["rsa5"]), REQUIRED_MARGIN
    )
    unrelated, reason, _rule, _also = decide(
        _lot(zoning_code="RM1"), _buy_box(zoning_codes=["RSA-5"]), REQUIRED_MARGIN
    )

    assert verdict == "BID"
    assert reversed_verdict == "BID"
    assert unrelated == "PASS"
    assert "RM1 is not one of your districts" in reason


def test_every_red_flag_carries_a_source_and_a_url() -> None:
    flags = red_flags(
        _lot(
            open_violation_count=2,
            most_recent_violation=date(2026, 3, 1),
            has_unsafe_structure=True,
            is_delinquent=True,
            total_due=12_500.0,
            delinquency_owner="ACME HOLDINGS LLC",
            city_neighbor=True,
            in_historic_district=True,
            in_flood_zone=True,
            overlays=("/NCA",),
        )
    )

    codes = {flag.code for flag in flags}
    assert codes == {
        "open_violations",
        "unsafe_structure",
        "tax_delinquent",
        "city_neighbor",
        "historic",
        "flood",
        "overlay",
    }
    assert all(flag.source and flag.source_url.startswith("http") for flag in flags)
    delinquency = next(flag for flag in flags if flag.code == "tax_delinquent")
    assert "ACME HOLDINGS LLC" in delinquency.detail
    assert "$12,500" in delinquency.detail
    violations = next(flag for flag in flags if flag.code == "open_violations")
    assert "2 open violations" in violations.detail
    assert "2026-03-01" in violations.detail


def test_a_delinquency_with_no_named_debtor_says_so_rather_than_inventing_one() -> None:
    flags = red_flags(_lot(is_delinquent=True, total_due=None, delinquency_owner=None))
    detail = next(flag for flag in flags if flag.code == "tax_delinquent").detail

    assert "an unnamed party" in detail
    assert "an unstated amount" in detail


def test_the_packet_splits_bid_look_and_pass_and_counts_the_header() -> None:
    packet = _compose(
        [
            _lot(parcel_number="phl:bid", est_margin=0.30),
            _lot(parcel_number="phl:look", opening_bid=90_000.0),
            _lot(parcel_number="phl:pass", est_margin=0.01),
            _lot(parcel_number="phl:house", is_vacant=False),
        ],
        _buy_box(max_bid=95_000),
    )

    assert packet.header.listings == 4
    assert packet.header.vacant == 3
    assert packet.header.passing_buy_box == 2
    assert [lot.verdict for lot in packet.lots] == ["BID", "LOOK"]
    assert [lot.parcel_number for lot in packet.passed] == ["phl:pass"]
    assert [lot.parcel_number for lot in packet.non_vacant_appendix] == ["phl:house"]


def test_bids_sort_before_looks_and_richer_margins_first() -> None:
    packet = _compose(
        [
            _lot(parcel_number="phl:thin", est_margin=0.22),
            _lot(parcel_number="phl:fat", est_margin=0.45),
            _lot(parcel_number="phl:look", opening_bid=90_000.0),
        ]
    )

    assert [lot.parcel_number for lot in packet.lots] == ["phl:fat", "phl:thin", "phl:look"]


def test_the_comp_range_spans_the_comps_given() -> None:
    comps = tuple(
        PacketComp(
            parcel_number=f"phl:c{index}",
            sale_price=price,
            reason="Nearby finished rowhouse.",
            source="rtt_summary",
            source_url="https://example.test",
        )
        for index, price in enumerate((210_000.0, 265_000.0, 240_000.0))
    )
    packet = _compose([_lot(comps=comps)])

    assert packet.lots[0].comp_range_low == 210_000.0
    assert packet.lots[0].comp_range_high == 265_000.0
    assert len(packet.lots[0].comps) == 3


def test_every_lot_carries_the_verify_before_bidding_list_naming_water_and_gas() -> None:
    packet = _compose([_lot()])
    joined = " ".join(packet.lots[0].verify_before_bidding).lower()

    assert "water" in joined
    assert "gas" in joined
    assert packet.verify_before_bidding == packet.lots[0].verify_before_bidding


def _adjacent(**overrides: object) -> AdjacentParcel:
    base: dict[str, object] = {
        "parcel_number": "phl:next",
        "address": "3 TEST ST",
        "owner_class": "vacant",
        "shared_boundary_ft": 40.0,
        "lot_area_sqft": 600.0,
    }
    base.update(overrides)
    return AdjacentParcel(**base)


def test_the_assemble_lens_bids_when_the_combined_footprint_clears_the_floor() -> None:
    verdict, reason, rule, _also = decide(
        _lot(lot_area_sqft=400.0, adjacent=(_adjacent(),)),
        _buy_box(target_use="assemble", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )

    assert verdict == "BID"
    assert "phl:next" in reason
    assert "[vacant]" in reason
    assert "1,000 sqft" in reason
    assert rule == "assemble: combined footprint by-right buildable under your floor"


def test_the_assemble_lens_looks_when_the_combined_footprint_still_falls_short() -> None:
    verdict, reason, rule, _also = decide(
        _lot(lot_area_sqft=200.0, adjacent=(_adjacent(lot_area_sqft=100.0, owner_class="public"),)),
        _buy_box(target_use="assemble", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )

    assert verdict == "LOOK"
    assert "[public]" in reason
    assert rule == "assemble: adjacent, combined footprint under your floor"


def test_the_assemble_lens_passes_with_no_qualifying_neighbour() -> None:
    verdict, reason, rule, _also = decide(
        _lot(adjacent=()), _buy_box(target_use="assemble"), REQUIRED_MARGIN
    )

    assert verdict == "PASS"
    assert "No adjacent vacant, publicly held or already-owned parcel" in reason
    assert rule == "assemble: no qualifying adjacent parcel"


def test_the_assemble_lens_names_a_parcel_you_already_own() -> None:
    _verdict, reason, _rule, _also = decide(
        _lot(lot_area_sqft=400.0, adjacent=(_adjacent(owner_class="owned_by_you"),)),
        _buy_box(target_use="assemble", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )

    assert "[owned_by_you]" in reason


def _priced(low: float, high: float) -> tuple[PacketComp, ...]:
    return tuple(
        PacketComp(
            parcel_number=f"phl:c{index}",
            sale_price=price,
            reason="Nearby land sale.",
            source="rtt_summary",
            source_url="https://example.test",
        )
        for index, price in enumerate((low, high))
    )


def test_the_flip_lens_bids_under_the_ratio_and_looks_under_the_comp_low() -> None:
    comps = _priced(100_000.0, 180_000.0)
    box = _buy_box(target_use="flip", flip_bid_ratio=0.70)

    cheap, cheap_reason, cheap_rule, _a = decide(
        _lot(opening_bid=60_000.0, comps=comps), box, REQUIRED_MARGIN
    )
    middling, _, middling_rule, _b = decide(
        _lot(opening_bid=90_000.0, comps=comps), box, REQUIRED_MARGIN
    )
    dear, _, dear_rule, _c = decide(_lot(opening_bid=120_000.0, comps=comps), box, REQUIRED_MARGIN)

    assert cheap == "BID"
    assert "$70,000" in cheap_reason
    assert cheap_rule == "hold/flip: opening bid <= 70% of comp low"
    assert middling == "LOOK"
    assert middling_rule == "hold/flip: opening bid <= comp low"
    assert dear == "PASS"
    assert dear_rule == "hold/flip: opening bid above comp low"


def test_the_flip_ratio_is_a_buy_box_field_that_moves_the_threshold() -> None:
    comps = _priced(100_000.0, 180_000.0)
    at_default, _, _r, _a = decide(
        _lot(opening_bid=75_000.0, comps=comps), _buy_box(target_use="flip"), REQUIRED_MARGIN
    )
    at_eighty, _, _r2, _a2 = decide(
        _lot(opening_bid=75_000.0, comps=comps),
        _buy_box(target_use="flip", flip_bid_ratio=0.80),
        REQUIRED_MARGIN,
    )

    assert BuyBoxWrite().flip_bid_ratio == DEFAULT_FLIP_BID_RATIO == 0.70
    assert at_default == "LOOK"
    assert at_eighty == "BID"


def test_the_flip_lens_does_not_gate_on_mao() -> None:
    comps = _priced(100_000.0, 180_000.0)
    verdict, _, _rule, _also = decide(
        _lot(opening_bid=60_000.0, comps=comps, max_allowable_offer=0.0, est_margin=-0.9),
        _buy_box(target_use="flip"),
        REQUIRED_MARGIN,
    )

    assert verdict == "BID"


def test_the_other_lenses_come_back_as_also_lines() -> None:
    _verdict, _reason, _rule, also = decide(
        _lot(comps=_priced(100_000.0, 180_000.0), adjacent=(_adjacent(),)),
        _buy_box(target_use="build", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )

    assert len(also) == 2
    assert any(line.startswith("also as assemble: ") for line in also)
    assert any(line.startswith("also as hold/flip: ") for line in also)


def test_a_hold_buyer_gets_build_and_assemble_as_also_lines() -> None:
    _verdict, _reason, _rule, also = decide(
        _lot(comps=_priced(100_000.0, 180_000.0)), _buy_box(target_use="hold"), REQUIRED_MARGIN
    )

    assert [line.split(":")[0] for line in also] == ["also as build", "also as assemble"]


def test_the_header_and_each_lot_carry_the_lens_and_when_it_was_computed() -> None:
    packet = _compose([_lot()], _buy_box(target_use="build"))

    assert packet.header.target_use == "build"
    assert packet.header.computed_at == GENERATED_AT
    assert packet.lots[0].graded_as == "build"
    assert packet.lots[0].computed_at == GENERATED_AT
    assert packet.lots[0].grade_rule.startswith("build: ")


def test_the_assemble_lens_does_not_pass_a_small_lot_on_its_own_size() -> None:
    verdict, _reason, rule, _also = decide(
        _lot(lot_area_sqft=300.0, adjacent=(_adjacent(lot_area_sqft=500.0),)),
        _buy_box(target_use="assemble", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )
    as_builder, builder_reason, _r, _a = decide(
        _lot(lot_area_sqft=300.0, adjacent=(_adjacent(lot_area_sqft=500.0),)),
        _buy_box(target_use="build", min_lot_sqft=640),
        REQUIRED_MARGIN,
    )

    assert verdict == "BID"
    assert rule == "assemble: combined footprint by-right buildable under your floor"
    assert as_builder == "PASS"
    assert "300 sqft is below your 640 sqft floor" in builder_reason
