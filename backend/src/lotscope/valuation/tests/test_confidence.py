import pytest

from lotscope.valuation.confidence import (
    CONFIDENCE_SCORE,
    NO_ESTIMATE_NOTE,
    ValueConfidence,
    value_confidence_band,
    value_support_note,
)


@pytest.mark.parametrize("band", ["high", "medium", "low"])
def test_every_stored_score_round_trips_to_its_band(band: ValueConfidence) -> None:
    assert value_confidence_band(CONFIDENCE_SCORE[band]) == band


def test_an_absent_score_has_no_band() -> None:
    assert value_confidence_band(None) is None


def test_scores_between_the_bands_fall_to_the_lower_one() -> None:
    assert value_confidence_band(0.89) == "medium"
    assert value_confidence_band(0.59) == "low"
    assert value_confidence_band(0.0) == "low"


def test_only_a_high_band_claims_the_sales_were_nearby() -> None:
    assert "nearby" in value_support_note("high")
    assert "rough guide" not in value_support_note("high")


def test_a_low_band_never_claims_the_sales_were_nearby() -> None:
    note = value_support_note("low")
    assert "nearby" not in note
    assert "rough guide" in note
    assert "none were found close by" in note


def test_a_medium_band_does_not_read_as_a_confident_estimate() -> None:
    note = value_support_note("medium")
    assert "indicative" in note


def test_no_estimate_is_stated_as_absence_not_as_a_low_estimate() -> None:
    assert value_support_note(None) == NO_ESTIMATE_NOTE
    assert "Not enough" in value_support_note(None)
