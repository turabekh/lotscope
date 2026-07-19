from lotscope.core.markets import Market, market_code
from lotscope.markets.seed import _SEED_MARKETS, WILMINGTON


def test_wilmington_slug_resolves_to_wlm_code() -> None:
    assert market_code("wilmington") == "wlm"
    assert market_code("wlm") == "wlm"
    assert Market.wilmington == "wilmington"


def test_wilmington_seed_row_is_a_delaware_pilot_in_2235() -> None:
    assert WILMINGTON in _SEED_MARKETS
    assert WILMINGTON["code"] == "wlm"
    assert WILMINGTON["state"] == "DE"
    assert WILMINGTON["url_slug"] == "wilmington"
    assert WILMINGTON["local_srid"] == 2235
    assert WILMINGTON["launch_status"] == "pilot"
    assert WILMINGTON["assessment_ratio"] == 1.0
    assert WILMINGTON["source_config"]["sheriff_civilview_county_id"] == "24"
    assert WILMINGTON["source_config"]["hundred_filter"] == "26"
