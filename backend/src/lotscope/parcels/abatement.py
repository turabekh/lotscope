def has_active_exemption(exempt_land: float | None, exempt_building: float | None) -> bool:
    return bool((exempt_building or 0.0) > 0.0 or (exempt_land or 0.0) > 0.0)
