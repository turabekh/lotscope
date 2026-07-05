from lotscope.core.markets import Market, market_code
from lotscope.markets.seed import HARRISBURG, _SEED_MARKETS


def test_harrisburg_slug_resolves_to_hbg_code() -> None:
    assert market_code("harrisburg") == "hbg"
    assert market_code("philadelphia") == "phl"
    assert market_code("hbg") == "hbg"
    assert Market.harrisburg == "harrisburg"


def test_harrisburg_seed_row_is_a_pilot_in_2272() -> None:
    assert HARRISBURG in _SEED_MARKETS
    assert HARRISBURG["code"] == "hbg"
    assert HARRISBURG["url_slug"] == "harrisburg"
    assert HARRISBURG["local_srid"] == 2272
    assert HARRISBURG["launch_status"] == "pilot"
    assert HARRISBURG["deal_assumption_overrides"]["deal_construction_cost_per_sqft"] == 145.0
    assert HARRISBURG["source_config"]["municipality_filter"] == "CITY OF HARRISBURG"
