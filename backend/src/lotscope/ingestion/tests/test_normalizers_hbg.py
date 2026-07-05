import pytest

from lotscope.ingestion.normalizers import (
    HbgKeyNormalizer,
    get_normalizer,
)


def test_hbg_preserves_real_property_id_format() -> None:
    n = HbgKeyNormalizer()
    assert n.normalize_local_key("01-001-020") == "01-001-020"
    assert n.normalize_local_key("04-038-028") == "04-038-028"
    assert n.normalize_local_key(" 04-038-028 ") == "04-038-028"


def test_hbg_reformats_digits_only_variant() -> None:
    n = HbgKeyNormalizer()
    assert n.normalize_local_key("04038028") == "04-038-028"


def test_hbg_accepts_optional_unit_segment() -> None:
    n = HbgKeyNormalizer()
    assert n.normalize_local_key("04-038-028-1") == "04-038-028-1"


def test_hbg_rejects_junk_and_empty() -> None:
    n = HbgKeyNormalizer()
    assert n.normalize_local_key(None) is None
    assert n.normalize_local_key("") is None
    assert n.normalize_local_key("not-a-parcel") is None
    assert n.normalize_local_key("881000253") is None


def test_hbg_to_canonical_prefixes_market() -> None:
    n = HbgKeyNormalizer()
    assert n.to_canonical("04-038-028") == "hbg:04-038-028"
    assert n.to_canonical("04038028") == "hbg:04-038-028"
    assert n.to_canonical(None) is None


def test_registry_exposes_hbg() -> None:
    assert get_normalizer("hbg").market == "hbg"
    with pytest.raises(KeyError):
        get_normalizer("pgh")
