from lotscope.ingestion.normalizers import WlmKeyNormalizer, get_normalizer

_N = WlmKeyNormalizer()


def test_real_firstmap_pins_pass_through() -> None:
    for pin in ["2600630067", "2600630068", "0600500019", "0600500020"]:
        assert _N.normalize_local_key(pin) == pin


def test_numeric_source_dropping_the_leading_zero_is_repadded() -> None:
    assert _N.normalize_local_key(600500019) == "0600500019"
    assert _N.normalize_local_key("600500019") == "0600500019"


def test_dashed_or_dotted_display_form_normalizes_to_10_digits() -> None:
    assert _N.normalize_local_key("26-0063-0067") == "2600630067"
    assert _N.normalize_local_key("26-006.30-067") == "2600630067"
    assert _N.normalize_local_key(" 2600630067 ") == "2600630067"


def test_invalid_shapes_rejected() -> None:
    assert _N.normalize_local_key(None) is None
    assert _N.normalize_local_key("") is None
    assert _N.normalize_local_key("26R-3") is None
    assert _N.normalize_local_key("26006300671") is None


def test_to_canonical_prefixes_market() -> None:
    assert _N.to_canonical("2600630067") == "wlm:2600630067"
    assert _N.to_canonical("bad") is None


def test_registered_under_wlm() -> None:
    assert get_normalizer("wlm").market == "wlm"
    assert get_normalizer("wlm").to_canonical("2600630067") == "wlm:2600630067"
