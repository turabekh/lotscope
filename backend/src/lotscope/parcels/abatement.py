def has_active_exemption(exempt_land: float | None, exempt_building: float | None) -> bool | None:
    if (exempt_building is not None and exempt_building > 0.0) or (
        exempt_land is not None and exempt_land > 0.0
    ):
        return True
    if exempt_building is None or exempt_land is None:
        return None
    return False
