import pytest

from lotscope.zoning.codes import normalize_zoning_code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("RSA-5", "RSA5"),
        ("rsa5", "RSA5"),
        ("RSA2", "RSA2"),
        ("CMX-2.5", "CMX2.5"),
        ("RM-1", "RM1"),
        (" cmx 2 ", "CMX2"),
    ],
)
def test_normalize_zoning_code(raw: str, expected: str) -> None:
    assert normalize_zoning_code(raw) == expected
