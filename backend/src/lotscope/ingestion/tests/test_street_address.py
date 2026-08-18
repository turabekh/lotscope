from lotscope.ingestion.street_address import normalize_street_address


def test_an_address_normalizes_to_a_stable_key() -> None:
    assert normalize_street_address("2138 N. Fairhill St.") == "2138 N FAIRHILL ST"


def test_spelled_out_suffixes_and_directions_collapse() -> None:
    assert normalize_street_address("1943 North Marshall Street") == "1943 N MARSHALL ST"
    assert normalize_street_address("8319 Childs Road") == "8319 CHILDS RD"


def test_case_punctuation_and_spacing_do_not_change_the_key() -> None:
    assert normalize_street_address("  1329   GROVE   ST  ") == normalize_street_address(
        "1329 Grove St."
    )


def test_a_unit_designator_is_dropped_so_a_building_matches_itself() -> None:
    assert normalize_street_address("100 MAIN ST APT 4B") == "100 MAIN ST"
    assert normalize_street_address("100 MAIN ST, Unit 12") == "100 MAIN ST"


def test_distinct_addresses_do_not_collide() -> None:
    assert normalize_street_address("2138 N FAIRHILL ST") != normalize_street_address(
        "2138 S FAIRHILL ST"
    )
    assert normalize_street_address("1329 GROVE ST") != normalize_street_address("1329 GROVE AVE")


def test_nothing_in_yields_nothing_out() -> None:
    assert normalize_street_address(None) is None
    assert normalize_street_address("") is None
    assert normalize_street_address("   ") is None
