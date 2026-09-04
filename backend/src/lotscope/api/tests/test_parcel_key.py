from lotscope.api.deps import canonicalize_parcel_key


def test_bare_key_gets_default_market_prefix() -> None:
    assert canonicalize_parcel_key("056219700") == "phl:056219700"
    assert canonicalize_parcel_key("000000001") == "phl:000000001"


def test_already_prefixed_key_is_unchanged() -> None:
    assert canonicalize_parcel_key("phl:056219700") == "phl:056219700"
    assert canonicalize_parcel_key("phl:000012345") == "phl:000012345"
