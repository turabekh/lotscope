from dataclasses import dataclass
from typing import Literal

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

LEAD_LIST_LIMITS: dict[str, int] = {
    "free": 8,
    "pro": 200,
    "enterprise": 1000,
}

WATCHLIST_LIMITS: dict[str, int | None] = {
    "free": 25,
    "pro": None,
    "enterprise": None,
}

PIPELINE_LIMITS: dict[str, int | None] = {
    "free": 10,
    "pro": None,
    "enterprise": None,
}


def ask_daily_limit(tier: str) -> int | None:
    return ASK_DAILY_LIMITS.get(tier, ASK_DAILY_LIMITS[_DEFAULT_TIER])


def lead_list_limit(tier: str) -> int:
    return LEAD_LIST_LIMITS.get(tier, LEAD_LIST_LIMITS[_DEFAULT_TIER])


def watchlist_limit(tier: str) -> int | None:
    return WATCHLIST_LIMITS.get(tier, WATCHLIST_LIMITS[_DEFAULT_TIER])


def pipeline_limit(tier: str) -> int | None:
    return PIPELINE_LIMITS.get(tier, PIPELINE_LIMITS[_DEFAULT_TIER])


def parcel_view_daily_limit(tier: str) -> int | None:
    return PARCEL_VIEW_DAILY_LIMITS.get(tier, PARCEL_VIEW_DAILY_LIMITS[_DEFAULT_TIER])


Action = Literal["current", "checkout", "contact"]


@dataclass(frozen=True)
class PlanCatalogEntry:
    tier: str
    name: str
    tagline: str
    price_monthly_cents: int | None
    price_annual_cents: int | None
    action: Action
    highlights: tuple[str, ...]


PLAN_CATALOG: tuple[PlanCatalogEntry, ...] = (
    PlanCatalogEntry(
        tier="free",
        name="Free",
        tagline="Explore Philadelphia parcels and verdicts.",
        price_monthly_cents=0,
        price_annual_cents=0,
        action="current",
        highlights=(
            "4 parcel verdicts per day",
            "10 AI questions per day",
            "Map, search, and buildability basics",
        ),
    ),
    PlanCatalogEntry(
        tier="pro",
        name="Pro",
        tagline="Unlimited research for serious investors and builders.",
        price_monthly_cents=2900,
        price_annual_cents=29000,
        action="checkout",
        highlights=(
            "Unlimited parcel verdicts",
            "200 AI questions per day",
            "Full comps, risk flags, and value ranges",
            "Priority recompute",
        ),
    ),
    PlanCatalogEntry(
        tier="enterprise",
        name="Enterprise",
        tagline="Teams, bulk exports, and API access.",
        price_monthly_cents=None,
        price_annual_cents=None,
        action="contact",
        highlights=(
            "Everything in Pro",
            "Unlimited AI questions",
            "Bulk export and API access",
            "Team seats and support",
        ),
    ),
)
