from lotscope.zoning.seed_pgh import PGH_STANDARDS


def _by_code() -> dict[str, dict]:
    return {r["code"]: r for r in PGH_STANDARDS}


def test_all_residential_suffixed_codes_present() -> None:
    codes = {r["code"] for r in PGH_STANDARDS}
    assert len(codes) == 18
    assert {"R1D-VL", "R1D-M", "R1D-H", "R1A-VH", "R2-M", "R3-L", "RM-H"} <= codes


def test_density_suffix_drives_distinct_standards() -> None:
    rows = _by_code()
    # RM height rises with density (corpus § 903.03): 40 -> 55 -> 85 -> 180
    assert rows["RM-M"]["max_height_ft"] == 55
    assert rows["RM-H"]["max_height_ft"] == 85
    assert rows["RM-VH"]["max_height_ft"] == 180
    # R1 stays 40 ft across densities
    assert rows["R1D-M"]["max_height_ft"] == 40
    assert rows["R1D-H"]["max_height_ft"] == 40
    # min lot shrinks: VL 6000, L 3000, M 2400, H 1200
    assert rows["R1D-VL"]["min_lot_area_sqft"] == 6000
    assert rows["R1D-L"]["min_lot_area_sqft"] == 3000
    assert rows["R1D-M"]["min_lot_area_sqft"] == 2400
    assert rows["R1D-H"]["min_lot_area_sqft"] == 1200


def test_unconfirmed_fields_are_null_not_guessed() -> None:
    rows = _by_code()
    # VH min lot lands on a page boundary in the corpus -> NULL, not guessed
    assert rows["R1D-VH"]["min_lot_area_sqft"] is None
    assert rows["RM-VH"]["min_lot_area_sqft"] is None
    # no row invents min_lot_width / occupancy / permitted_uses (use table not yet loaded)
    # min_lot_width has no district-wide dimensional floor (use-condition only) -> NULL stands
    for r in PGH_STANDARDS:
        assert "min_lot_width_ft" not in r


def test_by_right_units_from_district_type() -> None:
    rows = _by_code()
    assert rows["R1D-M"]["max_units"] == 1
    assert rows["R1A-H"]["max_units"] == 1
    assert rows["R2-M"]["max_units"] == 2
    assert rows["R3-L"]["max_units"] == 3
    # RM is envelope-governed -> estimated, not a firm by-right count
    assert rows["RM-H"]["max_units"] is None
    assert rows["RM-M"]["max_units"] is None


def test_primary_residential_use_authored() -> None:
    rows = _by_code()
    assert rows["R1D-M"]["permitted_uses"] == ["Single-Unit Detached Residential"]
    assert rows["R2-M"]["permitted_uses"] == ["Two-Unit Residential"]
    assert rows["RM-H"]["permitted_uses"] == ["Multi-Unit Residential"]
