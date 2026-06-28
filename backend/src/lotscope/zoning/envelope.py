_FLOOR_HEIGHT_FT = 10.5


def estimate_floors(height_ft: float | None) -> int | None:
    if height_ft is None or height_ft <= 0:
        return None
    return max(1, int(height_ft // _FLOOR_HEIGHT_FT))


def representative_inset_ft(
    front_setback_ft: float | None,
    side_setback_ft: float | None,
    rear_setback_ft: float | None,
) -> float:
    values = [v for v in (front_setback_ft, side_setback_ft, rear_setback_ft) if v is not None]
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)
