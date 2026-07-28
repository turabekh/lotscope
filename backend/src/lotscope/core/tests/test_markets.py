import pytest

from lotscope.core.errors import ValidationError
from lotscope.core.markets import (
    MARKET_CODES,
    MARKET_SLUGS,
    Market,
    market_argument,
    market_code,
)


def test_market_argument_defaults_to_every_market_when_the_flag_is_absent() -> None:
    assert market_argument([]) is None
    assert market_argument(["vacant"]) is None


def test_market_argument_resolves_slugs_and_codes() -> None:
    assert market_argument(["--market", "wilmington"]) == "wlm"
    assert market_argument(["--market", "wlm"]) == "wlm"
    assert market_argument(["vacant", "--market", "philadelphia"]) == "phl"


def test_market_argument_rejects_an_unknown_or_missing_value() -> None:
    with pytest.raises(ValidationError):
        market_argument(["--market", "atlantis"])
    with pytest.raises(ValidationError):
        market_argument(["--market"])


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
