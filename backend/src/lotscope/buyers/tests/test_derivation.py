from datetime import date

from lotscope.buyers.derivation import (
    BuyerSaleRow,
    derive_buyers,
    is_government_buyer,
)


def _row(
    grantee: str,
    *,
    grantor: str | None = "SELLER LLC",
    parcel: str = "phl:1",
    price: float = 5000.0,
    when: date = date(2026, 1, 1),
    vacant: bool = True,
    x: float | None = 100.0,
    y: float | None = 200.0,
) -> BuyerSaleRow:
    return BuyerSaleRow(
        grantor=grantor,
        grantee=grantee,
        parcel_number=parcel,
        sale_price=price,
        sale_date=when,
        is_vacant=vacant,
        centroid_x=x,
        centroid_y=y,
    )


def _n(name: str, count: int, **kw: object) -> list[BuyerSaleRow]:
    return [_row(name, parcel=f"phl:{name}:{i}", **kw) for i in range(count)]  # type: ignore[arg-type]


def test_qualifies_at_three_lot_purchases_not_two() -> None:
    assert derive_buyers(_n("THEDOOR LLC", 2)) == []
    result = derive_buyers(_n("THEDOOR LLC", 3))
    assert len(result) == 1
    assert result[0].buyer_key == "THEDOOR LLC"
    assert result[0].lot_purchases_window == 3


def test_min_purchases_override() -> None:
    assert len(derive_buyers(_n("BUYER LLC", 2), min_lot_purchases=2)) == 1


def test_related_party_sales_excluded() -> None:
    rows = [*_n("SMITH JOHN", 2), _row("SMITH JOHN", grantor="SMITH JOHN", parcel="phl:rp")]
    assert derive_buyers(rows) == []


def test_government_buyers_excluded() -> None:
    assert is_government_buyer("PHILADELPHIA LAND BANK") is True
    assert is_government_buyer("REDEVELOPMENT AUTHORITY OF PHILADELPHIA") is True
    assert is_government_buyer("THEDOOR LLC") is False
    assert derive_buyers(_n("PHILADELPHIA LAND BANK", 5)) == []


def test_nominal_price_sales_excluded() -> None:
    assert derive_buyers(_n("CHEAP LLC", 3, price=1.0)) == []
    assert len(derive_buyers(_n("CHEAP LLC", 3, price=1000.0))) == 1


def test_empty_or_blank_grantee_excluded() -> None:
    assert derive_buyers([_row("", parcel=f"phl:{i}") for i in range(3)]) == []
    assert derive_buyers([_row("   ", parcel=f"phl:{i}") for i in range(3)]) == []


def test_non_vacant_purchases_count_separately() -> None:
    rows = _n("MIXED LLC", 2) + _n("MIXED LLC", 3, vacant=False)
    assert derive_buyers(rows) == []
    rows2 = _n("MIXED LLC", 3) + _n("MIXED LLC", 2, vacant=False)
    result = derive_buyers(rows2)
    assert result[0].lot_purchases_window == 3
    assert result[0].purchases_window == 5


def test_key_normalization_groups_punctuation_variants() -> None:
    rows = [
        _row("T & I DEVELOPMENT, LLC", parcel="phl:a"),
        _row("T & I DEVELOPMENT LLC", parcel="phl:b"),
        _row("T & I  DEVELOPMENT  LLC.", parcel="phl:c"),
    ]
    result = derive_buyers(rows)
    assert len(result) == 1
    assert result[0].lot_purchases_window == 3


def test_stats_and_centroid() -> None:
    rows = [
        _row("STATS LLC", parcel="phl:a", price=2000.0, x=0.0, y=0.0, when=date(2025, 1, 1)),
        _row("STATS LLC", parcel="phl:b", price=4000.0, x=10.0, y=20.0, when=date(2026, 6, 1)),
        _row("STATS LLC", parcel="phl:c", price=6000.0, x=20.0, y=40.0, when=date(2025, 6, 1)),
    ]
    b = derive_buyers(rows)[0]
    assert b.median_price == 4000.0
    assert b.total_consideration == 12000.0
    assert b.centroid_x == 10.0
    assert b.centroid_y == 20.0
    assert b.last_purchase_at == date(2026, 6, 1)


def test_centroid_null_when_no_geometry() -> None:
    rows = _n("NOGEO LLC", 3, x=None, y=None)
    b = derive_buyers(rows)[0]
    assert b.centroid_x is None
    assert b.centroid_y is None


def test_display_name_uses_latest_purchase_spelling() -> None:
    rows = [
        _row("OLD NAME LLC", parcel="phl:a", when=date(2024, 1, 1)),
        _row("OLD NAME LLC", parcel="phl:b", when=date(2024, 2, 1)),
        _row("OLD NAME LLC", parcel="phl:c", when=date(2026, 1, 1)),
    ]
    assert derive_buyers(rows)[0].display_name == "OLD NAME LLC"
