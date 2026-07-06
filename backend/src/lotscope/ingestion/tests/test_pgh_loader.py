from lotscope.ingestion.loaders.pgh import _geometry_row, _parcel_row


def test_parcel_row_maps_assessment_fields() -> None:
    row = _parcel_row(
        {
            "PARID": "0001B00024000000",
            "PROPERTYADDRESS": "123 MAIN ST",
            "PROPERTYZIP": "15201",
            "USEDESC": "SINGLE FAMILY",
            "COUNTYTOTAL": "50000",
            "COUNTYLAND": "10000",
            "LOTAREA": "2472",
            "MUNIDESC": "4th Ward - PITTSBURGH",
        }
    )
    assert row is not None
    assert row["parcel_number"] == "pgh:0001B00024000000"
    assert row["market_code"] == "pgh"
    assert row["market_value"] == 50000.0
    assert row["lot_area_sqft"] == 2472.0
    assert row["lot_area_source"] == "extract"
    assert "local_key" not in row  # generated column


def test_parcel_row_skips_bad_parid() -> None:
    assert _parcel_row({"PARID": "123"}) is None


def test_geometry_row_builds_transformed_geom() -> None:
    row = _geometry_row({"PIN": "0001B00024000000", "wkb_hex": "00000000030000000100"})
    assert row is not None
    assert row["parcel_number"] == "pgh:0001B00024000000"
    assert "geom_4326" in row and "geom_local" in row


def test_geometry_row_skips_without_wkb() -> None:
    assert _geometry_row({"PIN": "0001B00024000000", "wkb_hex": None}) is None


def test_sale_row_filters_and_maps() -> None:
    from lotscope.ingestion.loaders.pgh import _sale_row

    known = {"pgh:0001B00024000000"}
    row = _sale_row(
        {"PARID": "0001B00024000000", "SALEDATE": "2024-03-15", "PRICE": "250000",
         "DEEDBOOK": "18965", "DEEDPAGE": "204", "INSTRTYPDESC": "DEED"},
        known,
    )
    assert row is not None
    assert row["document_id"] == "18965-204"
    assert row["sale_price"] == 250000.0
    assert row["sale_date"].isoformat() == "2024-03-15"


def test_sale_row_skips_unknown_parcel() -> None:
    from lotscope.ingestion.loaders.pgh import _sale_row

    assert _sale_row({"PARID": "0001B00024000000", "PRICE": "1"}, set()) is None


def test_pgh_forced_sale_named_treasurers_sale() -> None:
    from lotscope.markets.capabilities import forced_sale_label, forced_sale_surface_label

    assert forced_sale_surface_label("pgh") == "Treasurer's sale"
    assert forced_sale_label("pgh") == "Treasurer's sale"
    assert forced_sale_surface_label("phl") == "Sheriff sales"
