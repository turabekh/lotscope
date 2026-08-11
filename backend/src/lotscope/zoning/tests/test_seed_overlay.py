from lotscope.zoning.seed_overlay import TITLE_14_OVERLAY_STANDARDS

EXPECTED_SECTIONS = {
    "14-514": ("/FNE", "14-514(5)(a)"),
    "14-515": ("/NE", "14-515(2)(c)(.1)"),
    "14-520": ("/NDO", "14-520(4)(a)"),
    "14-524": ("/FDO", "14-524(2)(a)"),
    "14-530": ("/EDO", "14-530(2)"),
    "14-548": ("/SIX", "14-548(3)(a)(.3)"),
}


def test_every_overlay_that_raises_the_rsa5_minimum_is_seeded() -> None:
    seeded = {entry["code_section"] for entry in TITLE_14_OVERLAY_STANDARDS}

    assert seeded == set(EXPECTED_SECTIONS)


def test_each_overlay_carries_its_operative_subsection_and_code() -> None:
    for entry in TITLE_14_OVERLAY_STANDARDS:
        overlay_code, citation = EXPECTED_SECTIONS[entry["code_section"]]
        assert entry["overlay_code"] == overlay_code
        assert entry["citation"] == citation


def test_every_seeded_overlay_sets_the_same_rsa5_minimum() -> None:
    for entry in TITLE_14_OVERLAY_STANDARDS:
        assert entry["district_code"] == "RSA-5"
        assert entry["field"] == "min_lot_area_sqft"
        assert entry["value"] == 1440
