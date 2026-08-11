from lotscope.zoning.seed import TITLE_14_STANDARDS

TABLE_14_701_1_MIN_LOT_AREA = {
    "RSD-1": 10_000,
    "RSD-2": 7_800,
    "RSD-3": 5_000,
    "RSA-1": 5_000,
    "RSA-2": 3_150,
    "RSA-3": 2_250,
    "RSA-4": 1_620,
    "RSA-5": 960,
    "RSA-6": 700,
    "RTA-1": 2_250,
    "RTA-2": 1_080,
}


def _seeded() -> dict[str, float]:
    return {
        entry["code"]: entry["min_lot_area_sqft"]
        for entry in TITLE_14_STANDARDS
        if entry.get("min_lot_area_sqft") is not None
    }


def test_every_lower_density_district_matches_the_printed_table() -> None:
    seeded = _seeded()

    for code, expected in TABLE_14_701_1_MIN_LOT_AREA.items():
        assert seeded[code] == expected, f"{code} diverges from Table 14-701-1"


def test_rsa5_carries_the_base_minimum_not_the_overlay_one() -> None:
    assert _seeded()["RSA-5"] == 960
