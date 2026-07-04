from dataclasses import dataclass
from typing import Literal

_DEFAULT_TIER = "free"

ASK_DAILY_LIMITS: dict[str, int | None] = {
    "free": 10,
    "pro": 200,
    "investor": None,
    "enterprise": None,
}

PARCEL_VIEW_DAILY_LIMITS: dict[str, int | None] = {
    "free": 4,
    "pro": None,
    "investor": None,
    "enterprise": None,
}

LEAD_LIST_LIMITS: dict[str, int] = {
    "free": 8,
    "pro": 200,
    "investor": 1000,
    "enterprise": 1000,
}

WATCHLIST_LIMITS: dict[str, int | None] = {
    "free": 25,
    "pro": None,
    "investor": None,
    "enterprise": None,
}

PIPELINE_LIMITS: dict[str, int | None] = {
    "free": 10,
    "pro": None,
    "investor": None,
    "enterprise": None,
}

SAVED_SEARCH_LIMITS: dict[str, int | None] = {
    "free": 1,
    "pro": 50,
    "investor": None,
    "enterprise": None,
}

EXPORT_MONTHLY_LIMITS: dict[str, int | None] = {
    "free": 0,
    "pro": 10,
    "investor": None,
    "enterprise": None,
}

EXPORT_ROW_LIMITS: dict[str, int] = {
    "free": 0,
    "pro": 2000,
    "investor": 10000,
    "enterprise": 10000,
}


def ask_daily_limit(tier: str) -> int | None:
    return ASK_DAILY_LIMITS.get(tier, ASK_DAILY_LIMITS[_DEFAULT_TIER])


def lead_list_limit(tier: str) -> int:
    return LEAD_LIST_LIMITS.get(tier, LEAD_LIST_LIMITS[_DEFAULT_TIER])


def watchlist_limit(tier: str) -> int | None:
    return WATCHLIST_LIMITS.get(tier, WATCHLIST_LIMITS[_DEFAULT_TIER])


def pipeline_limit(tier: str) -> int | None:
    return PIPELINE_LIMITS.get(tier, PIPELINE_LIMITS[_DEFAULT_TIER])


def saved_search_limit(tier: str) -> int | None:
    return SAVED_SEARCH_LIMITS.get(tier, SAVED_SEARCH_LIMITS[_DEFAULT_TIER])


def parcel_view_daily_limit(tier: str) -> int | None:
    return PARCEL_VIEW_DAILY_LIMITS.get(tier, PARCEL_VIEW_DAILY_LIMITS[_DEFAULT_TIER])


def export_monthly_limit(tier: str) -> int | None:
    return EXPORT_MONTHLY_LIMITS.get(tier, EXPORT_MONTHLY_LIMITS[_DEFAULT_TIER])


def export_row_limit(tier: str) -> int:
    return EXPORT_ROW_LIMITS.get(tier, EXPORT_ROW_LIMITS[_DEFAULT_TIER])


FEED_TIERS = frozenset({"pro", "investor", "enterprise"})


def feed_access(tier: str) -> bool:
    return tier in FEED_TIERS


def sheriff_calendar_access(tier: str) -> bool:
    return tier in FEED_TIERS


def top_plays_access(tier: str) -> bool:
    return tier in FEED_TIERS


def report_access(tier: str) -> bool:
    return tier in FEED_TIERS


def market_stats_access(tier: str) -> bool:
    return tier in FEED_TIERS


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
        tagline="Full research for serious investors and builders.",
        price_monthly_cents=9900,
        price_annual_cents=99000,
        action="checkout",
        highlights=(
            "Unlimited parcel verdicts",
            "200 AI questions per day",
            "Full comps, risk flags, and value ranges",
            "200 motivated-seller leads",
        ),
    ),
    PlanCatalogEntry(
        tier="investor",
        name="Investor",
        tagline="The lead-gen machine: credits, exports, and the deal feed.",
        price_monthly_cents=24900,
        price_annual_cents=249000,
        action="checkout",
        highlights=(
            "Everything in Pro",
            "Unlimited AI questions",
            "1,000 leads with CSV export",
            "Daily deal feed and skip-trace credits",
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
