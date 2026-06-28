_DEFAULT_TIER = "free"

ASK_DAILY_LIMITS: dict[str, int | None] = {
    "free": 10,
    "pro": 200,
    "enterprise": None,
}

PARCEL_VIEW_DAILY_LIMITS: dict[str, int | None] = {
    "free": 4,
    "pro": None,
    "enterprise": None,
}


def ask_daily_limit(tier: str) -> int | None:
    return ASK_DAILY_LIMITS.get(tier, ASK_DAILY_LIMITS[_DEFAULT_TIER])


def parcel_view_daily_limit(tier: str) -> int | None:
    return PARCEL_VIEW_DAILY_LIMITS.get(tier, PARCEL_VIEW_DAILY_LIMITS[_DEFAULT_TIER])
