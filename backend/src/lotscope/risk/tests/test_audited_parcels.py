from datetime import date

from lotscope.distress.profiles import PHILLY_DISTRESS_V2
from lotscope.distress.scoring import DistressSignals, is_absentee, score_distress
from lotscope.risk.attribution import TransferAfterSnapshot, attribute_delinquency
from lotscope.risk.violation_status import is_open_violation

REGRESSION_PARCEL = "phl:201133900"
CONTROL_PARCEL = "phl:491313100"

_SNAPSHOT = "202206"

_REGRESSION_SHERIFF_DEED = TransferAfterSnapshot(
    grantor="MATUSOW JOSEPH",
    document_type="SHERIFF'S DEED",
    document_id="54321",
    sale_date=date(2025, 5, 8),
    sale_price=33900.0,
)


def test_the_audited_parcel_no_longer_calls_a_prior_owners_debt_a_deal_killer() -> None:
    result = attribute_delinquency(
        delinquency_owner="MATUSOW JOSEPH",
        current_owner="SHLAYEN RACHEL",
        snapshot_period=_SNAPSHOT,
        transfer=_REGRESSION_SHERIFF_DEED,
    )

    assert result.posture == "likely_discharged"
    assert result.counts_toward_distress is False
    assert "MATUSOW JOSEPH" in result.note
    assert "2025-05-08" in result.note
    assert "verify with the Dept. of Revenue" in result.note


def test_the_audited_parcels_closed_violation_is_not_open() -> None:
    assert is_open_violation("COMPLIED", "CLOSED") is False


def test_the_audited_parcel_loses_thirty_five_points_of_borrowed_distress() -> None:
    before = score_distress(
        DistressSignals(is_delinquent=True, total_due=8975.26, years_owed=44, open_violations=1),
        PHILLY_DISTRESS_V2,
    )
    after = score_distress(
        DistressSignals(is_delinquent=False, total_due=None, years_owed=None, open_violations=0),
        PHILLY_DISTRESS_V2,
    )

    assert before.score - after.score == 35
    assert {factor.code for factor in after.factors} == set()


def test_the_audited_parcels_owner_is_absentee_once_we_read_the_right_column() -> None:
    assert is_absentee("1943 N MARSHALL ST", None) is False
    assert is_absentee("1943 N MARSHALL ST", "8319 CHILDS RD WYNDMOOR PA 19038") is True


def test_the_control_parcels_debt_still_belongs_to_its_owner() -> None:
    result = attribute_delinquency(
        delinquency_owner="KENNEDY PATRICIA",
        current_owner="KENNEDY PATRICIA",
        snapshot_period=_SNAPSHOT,
        transfer=None,
    )

    assert result.posture == "current_owner"
    assert result.counts_toward_distress is True


def test_the_control_parcels_open_violations_still_count() -> None:
    assert is_open_violation("OPEN", "IN VIOLATION") is True


def test_the_control_parcel_keeps_every_point_it_had() -> None:
    signals = DistressSignals(
        is_delinquent=True, total_due=9189.94, years_owed=8, open_violations=2
    )

    scored = score_distress(signals, PHILLY_DISTRESS_V2)

    assert {factor.code for factor in scored.factors} == {
        "tax_delinquent",
        "severe_delinquency",
        "li_violations",
    }
    assert scored.score == 35


def test_the_control_parcels_owner_occupies_it_so_the_mailing_fix_changes_nothing() -> None:
    assert is_absentee("4941 N HUTCHINSON ST", None) is False
    assert (
        is_absentee("4941 N HUTCHINSON ST", "4941 N HUTCHINSON ST PHILADELPHIA PA 19141") is False
    )


def test_a_nominal_transfer_keeps_the_distress_signal_and_labels_it() -> None:
    result = attribute_delinquency(
        delinquency_owner="MATUSOW JOSEPH",
        current_owner="SHLAYEN RACHEL",
        snapshot_period=_SNAPSHOT,
        transfer=TransferAfterSnapshot(
            grantor="MATUSOW JOSEPH",
            document_type="DEED",
            document_id="7",
            sale_date=date(2024, 3, 1),
            sale_price=1.0,
        ),
    )

    assert result.counts_toward_distress is True
    assert "nominal consideration" in result.note


def test_an_ordinary_sale_keeps_the_flag_and_drops_the_owner_signal() -> None:
    result = attribute_delinquency(
        delinquency_owner="MATUSOW JOSEPH",
        current_owner="SHLAYEN RACHEL",
        snapshot_period=_SNAPSHOT,
        transfer=TransferAfterSnapshot(
            grantor="MATUSOW JOSEPH",
            document_type="DEED",
            document_id="99",
            sale_date=date(2024, 3, 1),
            sale_price=120000.0,
        ),
    )

    assert result.posture == "verify"
    assert result.counts_toward_distress is False
    assert "liens run with the land" in result.note
