import pytest

from lotscope.core.errors import ValidationError
from lotscope.core.markets import MARKET_CODES, MARKET_SLUGS, Market, market_code


def test_every_slug_resolves_to_a_code() -> None:
    assert {m.value for m in Market} == MARKET_SLUGS
    assert {market_code(slug) for slug in MARKET_SLUGS} == MARKET_CODES


def test_frontend_slugs_resolve_to_market_codes() -> None:
    assert market_code("philadelphia") == "phl"
    assert market_code("harrisburg") == "hbg"
    assert market_code("pittsburgh") == "pgh"
    assert market_code("wilmington") == "wlm"


def test_codes_pass_through_unchanged() -> None:
    assert market_code("phl") == "phl"
    assert market_code("hbg") == "hbg"
    assert market_code("pgh") == "pgh"
    assert market_code("wlm") == "wlm"


def test_unknown_market_is_rejected_rather_than_silently_passed_through() -> None:
    with pytest.raises(ValidationError):
        market_code("atlantis")


def test_every_market_code_matches_a_seeded_market() -> None:
    from lotscope.markets.seed import HARRISBURG, PHILADELPHIA, PITTSBURGH, WILMINGTON

    seeded = {m["code"] for m in (PHILADELPHIA, HARRISBURG, PITTSBURGH, WILMINGTON)}
    seeded_slugs = {m["url_slug"] for m in (PHILADELPHIA, HARRISBURG, PITTSBURGH, WILMINGTON)}
    assert seeded == MARKET_CODES
    assert seeded_slugs == MARKET_SLUGS
