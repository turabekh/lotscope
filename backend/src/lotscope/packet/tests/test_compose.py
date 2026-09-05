from datetime import UTC, date, datetime

from lotscope.buybox.schemas import BuyBoxRead, BuyBoxWrite
from lotscope.packet.compose import LotInputs, compose_packet, decide, is_scheduled, red_flags
from lotscope.packet.schemas import DataAsOf, PacketComp, PacketModel

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
    verdict, reason = decide(_lot(), _buy_box(max_bid=95_000), REQUIRED_MARGIN)

    assert verdict == "BID"
    assert "$60,000" in reason
    assert "28.0%" in reason


def test_an_offer_above_the_ceiling_is_a_pass() -> None:
    verdict, reason = decide(
        _lot(max_allowable_offer=150_000.0), _buy_box(max_bid=95_000), REQUIRED_MARGIN
    )

    assert verdict == "PASS"
    assert "$95,000 ceiling" in reason


def test_an_opening_bid_above_what_the_lot_supports_is_a_pass() -> None:
    verdict, reason = decide(_lot(opening_bid=90_000.0), _buy_box(), REQUIRED_MARGIN)

    assert verdict == "PASS"
    assert "opening bid" in reason.lower()


def test_a_margin_just_under_target_is_a_look_and_well_under_is_a_pass() -> None:
    near, near_reason = decide(_lot(est_margin=0.17), _buy_box(), REQUIRED_MARGIN)
    far, _ = decide(_lot(est_margin=0.02), _buy_box(), REQUIRED_MARGIN)

    assert near == "LOOK"
    assert "turns on the assumptions" in near_reason
    assert far == "PASS"


def test_a_high_severity_flag_downgrades_a_bid_to_look() -> None:
    verdict, reason = decide(_lot(is_delinquent=True, total_due=9_000.0), _buy_box(), 0.20)

    assert verdict == "LOOK"
    assert "tax delinquency" in reason.lower()


def test_no_computable_offer_is_a_look_not_a_silent_pass() -> None:
    verdict, reason = decide(
        _lot(max_allowable_offer=None, est_margin=None), _buy_box(), REQUIRED_MARGIN
    )

    assert verdict == "LOOK"
    assert "manual read" in reason


def test_nothing_buildable_by_right_is_a_pass() -> None:
    verdict, reason = decide(_lot(can_build_by_right=False), _buy_box(), REQUIRED_MARGIN)

    assert verdict == "PASS"
    assert "variance" in reason


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
        verdict, reason = decide(_lot(**lot_kwargs), _buy_box(**box_kwargs), REQUIRED_MARGIN)
        assert verdict == "PASS", (lot_kwargs, reason)
        assert expected in reason.lower(), (lot_kwargs, reason)


def test_a_hyphenated_buy_box_code_matches_the_hyphenless_one_the_city_stores() -> None:
    verdict, _ = decide(_lot(zoning_code="RSA5"), _buy_box(zoning_codes=["RSA-5"]), REQUIRED_MARGIN)
    reversed_verdict, _ = decide(
        _lot(zoning_code="RSA-5"), _buy_box(zoning_codes=["rsa5"]), REQUIRED_MARGIN
    )
    unrelated, reason = decide(
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
            _lot(parcel_number="phl:look", est_margin=0.17),
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
            _lot(parcel_number="phl:look", est_margin=0.17),
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
