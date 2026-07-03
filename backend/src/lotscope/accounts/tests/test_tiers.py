from lotscope.accounts.tiers import (
    PLAN_CATALOG,
    ask_daily_limit,
    lead_list_limit,
    pipeline_limit,
    saved_search_limit,
    watchlist_limit,
)


def test_ask_daily_limit_known_tiers() -> None:
    assert ask_daily_limit("free") == 10
    assert ask_daily_limit("pro") == 200
    assert ask_daily_limit("enterprise") is None


def test_ask_daily_limit_unknown_tier_falls_back_to_free() -> None:
    assert ask_daily_limit("mystery") == 10


def test_investor_limits_sit_between_pro_and_unlimited() -> None:
    assert ask_daily_limit("investor") is None
    assert watchlist_limit("investor") is None
    assert pipeline_limit("investor") is None
    assert saved_search_limit("investor") is None
    assert lead_list_limit("investor") == 1000


def test_catalog_offers_four_plans_with_repriced_pro_and_investor() -> None:
    by_tier = {entry.tier: entry for entry in PLAN_CATALOG}
    assert set(by_tier) == {"free", "pro", "investor", "enterprise"}

    pro = by_tier["pro"]
    assert pro.price_monthly_cents == 9900
    assert pro.price_annual_cents == 99000
    assert pro.action == "checkout"

    investor = by_tier["investor"]
    assert investor.price_monthly_cents == 24900
    assert investor.price_annual_cents == 249000
    assert investor.action == "checkout"

    assert by_tier["enterprise"].action == "contact"


def test_catalog_orders_investor_after_pro() -> None:
    order = [entry.tier for entry in PLAN_CATALOG]
    assert order.index("pro") < order.index("investor") < order.index("enterprise")
