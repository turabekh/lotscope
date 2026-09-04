_PHL_VACANT_USES = frozenset(
    {
        "VACANT LAND",
        "VACANT LAND - RESIDENTIAL",
        "VACANT LAND - NON-RESIDENTIAL",
    }
)

VACANT_LAND_USES = _PHL_VACANT_USES

_IMPROVEMENT_THRESHOLD = 1000.0
DERIVED_MULTI_SIGNAL = 0.5
DERIVED_SINGLE_SIGNAL = 0.35


def derive_vacancy(
    land_use: str | None, improvement_value: float | None
) -> tuple[bool, float | None]:
    if land_use is None or land_use.strip().upper() not in VACANT_LAND_USES:
        return False, None
    if improvement_value is not None and improvement_value >= _IMPROVEMENT_THRESHOLD:
        return False, None
    if improvement_value is None:
        return True, DERIVED_SINGLE_SIGNAL
    return True, DERIVED_MULTI_SIGNAL
