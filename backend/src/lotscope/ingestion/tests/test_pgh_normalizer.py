from lotscope.ingestion.normalizers import PghKeyNormalizer

_N = PghKeyNormalizer()


def test_real_parids_pass_through() -> None:
    for parid in ["0001B00024000000", "0001G00224060600", "0173C00181000000", "0001H00327170100"]:
        assert _N.normalize_local_key(parid) == parid


def test_dashed_display_form_normalizes_to_16char() -> None:
    assert _N.normalize_local_key("0001-B-00024-0000-00") == "0001B00024000000"
    assert _N.normalize_local_key(" 0173C00181000000 ") == "0173C00181000000"


def test_lowercase_uppercased() -> None:
    assert _N.normalize_local_key("0001b00024000000") == "0001B00024000000"


def test_invalid_shapes_rejected() -> None:
    assert _N.normalize_local_key(None) is None
    assert _N.normalize_local_key("") is None
    assert _N.normalize_local_key("123") is None
    assert _N.normalize_local_key("0001B000240000000") is None  # 17 chars
    assert _N.normalize_local_key("0001B0002400000") is None  # 15 chars


def test_to_canonical_prefixes_market() -> None:
    assert _N.to_canonical("0001B00024000000") == "pgh:0001B00024000000"
    assert _N.to_canonical("bad") is None
