_HBG_VACANT_USES = frozenset(
    {
        "BLDG LOT UNDER 1 ACRE",
        "BLDG LOT 1 TO 5 ACRES",
        "BLDG LOT OVER 5 ACRES",
        "RESIDENTIAL DEV LAND",
        "COMMERCIAL LAND",
        "INDUSTRIAL LAND",
        "MISCELLANEOUS LAND",
        "UNBUILDABLE LOT",
    }
)

_PGH_VACANT_USES = frozenset(
    {
        "VACANT LAND",
        "VACANT COMMERCIAL LAND",
        "VACANT INDUSTRIAL LAND",
        ">10 ACRES VACANT",
    }
)

_PHL_VACANT_USES = frozenset(
    {
        "VACANT LAND",
        "VACANT LAND - RESIDENTIAL",
        "VACANT LAND - NON-RESIDENTIAL",
    }
)

VACANT_LAND_USES_BY_MARKET: dict[str, frozenset[str]] = {
    "hbg": _HBG_VACANT_USES,
    "pgh": _PGH_VACANT_USES,
    "phl": _PHL_VACANT_USES,
}

_IMPROVEMENT_THRESHOLD = 1000.0
DERIVED_MULTI_SIGNAL = 0.5
DERIVED_SINGLE_SIGNAL = 0.35


def derive_vacancy(
    land_use: str | None, improvement_value: float | None, market_code: str
) -> tuple[bool, float | None]:
    vacant_uses = VACANT_LAND_USES_BY_MARKET.get(market_code, frozenset())
    if land_use is None or land_use.strip().upper() not in vacant_uses:
        return False, None
    if improvement_value is not None and improvement_value >= _IMPROVEMENT_THRESHOLD:
        return False, None
    if improvement_value is None:
        return True, DERIVED_SINGLE_SIGNAL
    return True, DERIVED_MULTI_SIGNAL
