import pytest

from lotscope.ingestion.normalizers import (
    KEY_NORMALIZERS,
    PhlKeyNormalizer,
    get_normalizer,
)


def test_phl_normalizes_local_key_to_zero_padded_nine_digits() -> None:
    n = PhlKeyNormalizer()
    assert n.normalize_local_key("1234567") == "001234567"
    assert n.normalize_local_key("881000253") == "881000253"
    assert n.normalize_local_key("  012-345-678 ") == "012345678"


def test_phl_rejects_over_length_or_empty() -> None:
    n = PhlKeyNormalizer()
    assert n.normalize_local_key(None) is None
    assert n.normalize_local_key("") is None
    assert n.normalize_local_key("1234567890") is None


def test_phl_to_canonical_prefixes_market() -> None:
    n = PhlKeyNormalizer()
    assert n.to_canonical("1234567") == "phl:001234567"
    assert n.to_canonical(None) is None


def test_registry_is_market_keyed_and_phl_only() -> None:
    assert set(KEY_NORMALIZERS) == {"phl"}
    assert get_normalizer("phl").market == "phl"
    with pytest.raises(KeyError):
        get_normalizer("hbg")
