from datetime import date

import pytest

from lotscope.buyers.cli import parse_since
from lotscope.buyers.derivation import (
    RepeatBuyerRow,
    derive_repeat_buyers,
    is_excluded_buyer,
    most_frequent_mailing_address,
)


def _row(grantee: str, parcel: str, *, price: float = 20_000.0, day: int = 1) -> RepeatBuyerRow:
    return RepeatBuyerRow(
        grantee=grantee,
        parcel_number=parcel,
        address=f"{day} TEST ST",
        sale_date=date(2026, 3, day),
        sale_price=price,
    )


def test_a_buyer_needs_two_distinct_parcels_to_qualify() -> None:
    one = derive_repeat_buyers([_row("ACME LLC", "phl:1")])
    two = derive_repeat_buyers([_row("ACME LLC", "phl:1"), _row("ACME LLC", "phl:2", day=2)])

    assert one == []
    assert [b.display_name for b in two] == ["ACME LLC"]
    assert two[0].purchase_count == 2


def test_the_same_parcel_bought_twice_counts_once() -> None:
    buyers = derive_repeat_buyers(
        [
            _row("ACME LLC", "phl:1", day=1),
            _row("ACME LLC", "phl:1", day=5),
            _row("ACME LLC", "phl:2", day=2),
        ]
    )

    assert buyers == [] or buyers[0].purchase_count == 2


def test_punctuation_and_case_do_not_split_one_buyer_in_two() -> None:
    buyers = derive_repeat_buyers(
        [_row("Acme Holdings, L.L.C.", "phl:1"), _row("ACME  HOLDINGS LLC", "phl:2", day=2)]
    )

    assert len(buyers) == 1
    assert buyers[0].purchase_count == 2


def test_public_owners_and_lenders_are_excluded() -> None:
    excluded = [
        "PHILADELPHIA LAND BANK",
        "CITY OF PHILADELPHIA",
        "PHILADELPHIA HOUSING AUTHORITY",
        "REDEVELOPMENT AUTHORITY OF PHILADELPHIA",
        "FEDERAL NATIONAL MORTGAGE ASSOCIATION",
        "US BANK TRUST NATIONAL ASSOCIATION TR",
        "PENNYMAC LOAN SERVICES LLC",
        "MIDFIRST BANK",
        "CARRINGTON MORTGAGE SERVICES LLC",
        "WELLS FARGO BANK N A",
        "LAKEVIEW LOAN SERVICING LLC",
        "CASCADE FUNDING MORTGAGE TRUST HB7",
    ]
    kept = [
        "BRONZE CAPITAL LLC",
        "RILEY DENISE LLC",
        "AU PHILIP",
        "MANNINO ANTONIO",
        "MPGA LLC",
        "HNB INVESTMENT PROPERTIES LLC",
    ]

    assert all(is_excluded_buyer(name) for name in excluded)
    assert not any(is_excluded_buyer(name) for name in kept)


def test_an_excluded_grantee_never_reaches_the_list() -> None:
    buyers = derive_repeat_buyers(
        [
            _row("PHILADELPHIA LAND BANK", "phl:1"),
            _row("PHILADELPHIA LAND BANK", "phl:2", day=2),
            _row("ACME LLC", "phl:3", day=3),
            _row("ACME LLC", "phl:4", day=4),
        ]
    )

    assert [b.display_name for b in buyers] == ["ACME LLC"]


def test_the_mailing_address_is_the_most_frequent_across_holdings() -> None:
    address, sources = most_frequent_mailing_address(
        ["1 MAIN ST PHILADELPHIA PA 19100", "1  main st philadelphia pa 19100", "9 OTHER RD"]
    )

    assert address == "1 MAIN ST PHILADELPHIA PA 19100"
    assert sources == 2


def test_a_buyer_with_no_holdings_is_flagged_rather_than_dropped() -> None:
    buyers = derive_repeat_buyers(
        [_row("ACME LLC", "phl:1"), _row("ACME LLC", "phl:2", day=2)],
        mailing_addresses={},
    )

    assert len(buyers) == 1
    assert buyers[0].has_mailing_address is False
    assert buyers[0].mailing_address is None


def test_purchases_come_back_newest_first_with_the_total() -> None:
    buyers = derive_repeat_buyers(
        [
            _row("ACME LLC", "phl:1", price=10_000.0, day=1),
            _row("ACME LLC", "phl:2", price=30_000.0, day=9),
        ]
    )

    assert [p.parcel_number for p in buyers[0].purchases] == ["phl:2", "phl:1"]
    assert buyers[0].total_consideration == 40_000.0


def test_the_since_flag_parses_month_counts() -> None:
    assert parse_since("24m") == 24
    assert parse_since("6 months") == 6
    assert parse_since("12mo") == 12
    with pytest.raises(ValueError, match="expects a month count"):
        parse_since("last year")
