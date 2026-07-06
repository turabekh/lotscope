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
    assert "geom_4326" in row
    assert "geom_local" in row


def test_geometry_row_skips_without_wkb() -> None:
    assert _geometry_row({"PIN": "0001B00024000000", "wkb_hex": None}) is None


def test_sale_row_filters_and_maps() -> None:
    from lotscope.ingestion.loaders.pgh import _sale_row

    known = {"pgh:0001B00024000000"}
    row = _sale_row(
        {
            "PARID": "0001B00024000000",
            "SALEDATE": "2024-03-15",
            "PRICE": "250000",
            "DEEDBOOK": "18965",
            "DEEDPAGE": "204",
            "INSTRTYPDESC": "DEED",
        },
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


def test_pgh_hidden_surfaces_owner_and_forced_sale_off() -> None:
    from lotscope.markets.capabilities import hidden_surfaces

    hidden = hidden_surfaces("pgh")
    assert "owner_portfolio" in hidden  # Ordinance 3478-07
    assert "zba_variance" in hidden
    assert "sheriff_sales" in hidden  # hidden until foreclosure calendar exists


def test_violation_row_maps_and_filters() -> None:
    from lotscope.ingestion.loaders.pgh import _violation_row

    known = {"pgh:0042M00227000000"}
    row = _violation_row(
        {
            "parcel_id": "0042M00227000000",
            "casefile_number": "CF-2026-1",
            "status": "In Violation",
            "investigation_date": "2026-01-10",
            "violation_description": "Overgrowth",
        },
        known,
    )
    assert row is not None
    assert row["event_type"] == "violation"
    assert row["status"] == "OPEN"
    assert row["external_id"] == "CF-2026-1"


def test_violation_row_skips_unknown_parcel() -> None:
    from lotscope.ingestion.loaders.pgh import _violation_row

    assert _violation_row({"parcel_id": "0042M00227000000", "casefile_number": "X"}, set()) is None


def test_condemned_status_is_not_read_by_risk_scoring() -> None:
    # condemned/dead-end is an unscored fact — the risk service source must not reference it
    import inspect

    from lotscope.risk import service

    assert "condemned_status" not in inspect.getsource(service)


def test_district_row_maps_code_and_geometry() -> None:
    from lotscope.ingestion.loaders.pgh import _district_row

    row = _district_row(
        {
            "_id": "42",
            "zon_new": "R1D-M",
            "full_zoning_type": "SINGLE-UNIT DETACHED RESIDENTIAL",
            "geometry": (
                "POLYGON ((592821 4468479, 592822 4468479, "
                "592822 4468480, 592821 4468479))"
            ),
        }
    )
    assert row is not None
    assert row["code"] == "R1D-M"
    assert row["external_id"] == "pgh:42"
    assert "geom_local" in row
    assert "geom_4326" in row


def test_district_row_skips_without_code_or_geom() -> None:
    from lotscope.ingestion.loaders.pgh import _district_row

    assert _district_row({"_id": "1", "zon_new": None, "geometry": "POLYGON(())"}) is None
    assert _district_row({"_id": "1", "zon_new": "R1D-M", "geometry": None}) is None
