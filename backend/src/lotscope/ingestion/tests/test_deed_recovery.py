from lotscope.ingestion.deed_recovery import (
    RESOLVED,
    UNRESOLVED_COLLISION,
    UNRESOLVED_NO_ADDRESS,
    UNRESOLVED_NO_MATCH,
    build_address_index,
    recover_parcel,
    summarise,
)

_INDEX = build_address_index(
    [
        ("phl:191357500", "2138 N FAIRHILL ST"),
        ("phl:201133900", "1943 N MARSHALL ST"),
        ("phl:100000001", "50 SHARED ST"),
        ("phl:100000002", "50 Shared Street"),
        ("phl:100000003", None),
    ]
)


def test_a_deed_address_recovers_its_parcel() -> None:
    outcome = recover_parcel("2138 N. Fairhill St.", _INDEX)

    assert outcome.parcel_number == "phl:191357500"
    assert outcome.reason == RESOLVED


def test_two_parcels_on_one_address_leave_the_deed_unattributed() -> None:
    outcome = recover_parcel("50 SHARED ST", _INDEX)

    assert outcome.parcel_number is None
    assert outcome.reason == UNRESOLVED_COLLISION


def test_an_address_we_do_not_hold_is_unattributed_not_guessed() -> None:
    outcome = recover_parcel("999 NOWHERE AVE", _INDEX)

    assert outcome.parcel_number is None
    assert outcome.reason == UNRESOLVED_NO_MATCH


def test_a_deed_with_no_address_is_unattributed() -> None:
    for value in (None, "", "   "):
        outcome = recover_parcel(value, _INDEX)
        assert outcome.parcel_number is None
        assert outcome.reason == UNRESOLVED_NO_ADDRESS


def test_the_same_parcel_listed_twice_is_not_a_collision() -> None:
    index = build_address_index([("phl:1", "10 A ST"), ("phl:1", "10 A Street")])

    assert recover_parcel("10 A ST", index).parcel_number == "phl:1"


def test_parcels_without_an_address_never_enter_the_index() -> None:
    assert all(key is not None for key in _INDEX)


def test_outcomes_summarise_by_reason_so_drops_are_counted_not_silent() -> None:
    outcomes = [
        recover_parcel("2138 N FAIRHILL ST", _INDEX),
        recover_parcel("50 SHARED ST", _INDEX),
        recover_parcel("999 NOWHERE AVE", _INDEX),
        recover_parcel(None, _INDEX),
    ]

    counts = summarise(outcomes)

    assert counts[RESOLVED] == 1
    assert counts[UNRESOLVED_COLLISION] == 1
    assert counts[UNRESOLVED_NO_MATCH] == 1
    assert counts[UNRESOLVED_NO_ADDRESS] == 1
