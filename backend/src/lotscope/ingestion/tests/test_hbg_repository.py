from lotscope.ingestion.loaders.hbg_repository import (
    classify_repository_row,
    parse_repository_pdf_text,
)


def _row(**over):
    base = {
        "parcel_number": "02-030-005",
        "site_address": "409 S 14th St",
        "municipality": "City of Hbg.",
        "assessed_type": "Land",
        "hbg_city_status": "Demolished",
        "bid_pending": "false",
        "list_as_of": "2026-06-25",
        "source_url": "http://x/repo.pdf",
    }
    base.update(over)
    return base


def test_classify_keeps_harrisburg_city_normalizes_key() -> None:
    r = classify_repository_row(_row())
    assert r is not None
    assert r["parcel_number"] == "hbg:02-030-005"
    assert r["city_status"] == "Demolished"
    assert r["bid_pending"] is False


def test_classify_skips_non_city_municipality() -> None:
    assert classify_repository_row(_row(municipality="Steelton Boro")) is None


def test_classify_skips_long_trailer_key_shape() -> None:
    # the long trailer form is not a standard MM-BBB-PPP hbg key
    assert classify_repository_row(_row(parcel_number="310070140000000")) is None


def test_bid_pending_true_parsed() -> None:
    r = classify_repository_row(_row(bid_pending="true"))
    assert r is not None and r["bid_pending"] is True


def test_pdf_parser_produces_the_csv_schema() -> None:
    text = "01-035-023 1315 S 12th St City of Hbg. Land Demolished\nSteelton 99-999-999 Elsewhere"
    rows = parse_repository_pdf_text(text, list_as_of="2026-06-25")
    assert rows[0]["parcel_number"] == "01-035-023"
    assert rows[0]["municipality"] == "City of Hbg."
    assert rows[0]["hbg_city_status"] == "Demolished"
    # both paths feed classify_repository_row -> identical downstream schema
    assert classify_repository_row(rows[0]) is not None
