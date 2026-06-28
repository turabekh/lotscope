import pytest

from lotscope.zoning.envelope import estimate_floors, representative_inset_ft


@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (None, None),
        (0.0, None),
        (-5.0, None),
        (10.5, 1),
        (38.0, 3),
        (35.0, 3),
    ],
)
def test_estimate_floors(height: float | None, expected: int | None) -> None:
    assert estimate_floors(height) == expected


def test_representative_inset_averages_present_setbacks() -> None:
    assert representative_inset_ft(8.0, 0.0, 9.0) == pytest.approx(5.67)


def test_representative_inset_ignores_missing() -> None:
    assert representative_inset_ft(None, 5.0, None) == 5.0


def test_representative_inset_defaults_to_zero() -> None:
    assert representative_inset_ft(None, None, None) == 0.0
