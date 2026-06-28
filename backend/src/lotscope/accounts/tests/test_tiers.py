from lotscope.accounts.tiers import ask_daily_limit


def test_ask_daily_limit_known_tiers() -> None:
    assert ask_daily_limit("free") == 10
    assert ask_daily_limit("pro") == 200
    assert ask_daily_limit("enterprise") is None


def test_ask_daily_limit_unknown_tier_falls_back_to_free() -> None:
    assert ask_daily_limit("mystery") == 10
