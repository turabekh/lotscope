from datetime import date

from lotscope.risk.attribution import (
    DelinquencyAttribution,
    TransferAfterSnapshot,
    attribute_delinquency,
)

_SNAPSHOT = "202206"

_SHERIFF = TransferAfterSnapshot(
    grantor="MATUSOW JOSEPH",
    document_type="SHERIFF'S DEED",
    document_id="54321",
    sale_date=date(2025, 5, 8),
    sale_price=33900.0,
)


def _attribute(**overrides: object) -> DelinquencyAttribution:
    kwargs: dict[str, object] = {
        "delinquency_owner": "MATUSOW JOSEPH",
        "current_owner": "SHLAYEN RACHEL",
        "snapshot_period": _SNAPSHOT,
        "transfer": _SHERIFF,
    }
    kwargs.update(overrides)
    return attribute_delinquency(**kwargs)  # type: ignore[arg-type]


def test_a_sheriff_sale_from_the_debtor_is_likely_discharged_and_leaves_distress() -> None:
    result = _attribute()

    assert result.posture == "likely_discharged"
    assert result.counts_toward_distress is False
    assert "MATUSOW JOSEPH" in result.note
    assert "2025-05-08" in result.note
    assert "doc 54321" in result.note
    assert "verify with the Dept. of Revenue" in result.note


def test_a_debt_owed_by_the_current_owner_is_untouched() -> None:
    result = _attribute(delinquency_owner="SHLAYEN RACHEL", transfer=None)

    assert result.posture == "current_owner"
    assert result.counts_toward_distress is True


def test_an_ordinary_sale_keeps_the_flag_but_drops_the_owner_signal() -> None:
    result = _attribute(
        transfer=TransferAfterSnapshot(
            grantor="MATUSOW JOSEPH",
            document_type="DEED",
            document_id="99",
            sale_date=date(2024, 3, 1),
            sale_price=120000.0,
        )
    )

    assert result.posture == "verify"
    assert result.counts_toward_distress is False
    assert "liens run with the land" in result.note


def test_a_nominal_transfer_keeps_the_distress_signal_and_says_why() -> None:
    result = _attribute(
        transfer=TransferAfterSnapshot(
            grantor="MATUSOW JOSEPH",
            document_type="DEED",
            document_id="7",
            sale_date=date(2024, 3, 1),
            sale_price=1.0,
        )
    )

    assert result.counts_toward_distress is True
    assert "nominal consideration" in result.note


def test_a_nominal_sheriff_deed_still_keeps_the_signal() -> None:
    result = _attribute(
        transfer=TransferAfterSnapshot(
            grantor="MATUSOW JOSEPH",
            document_type="SHERIFF'S DEED",
            document_id="7",
            sale_date=date(2025, 1, 1),
            sale_price=0.0,
        )
    )

    assert result.counts_toward_distress is True


def test_a_partial_match_against_the_current_owner_keeps_the_signal_and_labels_it() -> None:
    result = _attribute(delinquency_owner="RACHEL SHLAYEN")

    assert result.posture == "current_owner"
    assert result.counts_toward_distress is True
    assert "ambiguous" in result.note


def test_an_unnamed_debtor_keeps_everything_and_says_the_source_is_silent() -> None:
    result = _attribute(delinquency_owner=None)

    assert result.posture == "unknown_debtor"
    assert result.counts_toward_distress is True
    assert "does not name who owes it" in result.note


def test_a_stranger_debt_with_no_transfer_asks_for_verification() -> None:
    result = _attribute(transfer=None)

    assert result.posture == "verify"
    assert result.counts_toward_distress is False
    assert "No later transfer" in result.note


def test_a_sheriff_deed_from_an_unrelated_grantor_is_not_discharged() -> None:
    result = _attribute(
        transfer=TransferAfterSnapshot(
            grantor="SOMEONE ELSE ENTIRELY",
            document_type="SHERIFF'S DEED",
            document_id="1",
            sale_date=date(2025, 1, 1),
            sale_price=50000.0,
        )
    )

    assert result.posture == "verify"


def test_every_note_states_the_snapshot_vintage() -> None:
    for result in (_attribute(), _attribute(delinquency_owner=None), _attribute(transfer=None)):
        assert "2022-06" in result.note or "recorded snapshot" in result.note
