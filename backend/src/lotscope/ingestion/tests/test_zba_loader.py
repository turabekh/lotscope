from datetime import date

from lotscope.ingestion.loaders.zba import ZbaRecord, to_zba_row


def test_to_zba_row_maps_appeal_fields_and_reconciles_parcel() -> None:
    row = to_zba_row(
        ZbaRecord(
            appealnumber="18756",
            opa_account_num="882966695",
            applicationtype="RB_ZBA",
            decision="GRANTED/PROV",
            decisiondate="2013-02-27T21:00:00Z",
            address="2324 PALETHORP ST",
        )
    )
    assert row is not None
    assert row["appeal_number"] == "18756"
    assert row["parcel_number"] == "phl:882966695"
    assert row["appeal_type"] == "RB_ZBA"
    assert row["decision"] == "GRANTED/PROV"
    assert row["decision_date"] == date(2013, 2, 27)
    assert row["address"] == "2324 PALETHORP ST"


def test_to_zba_row_keeps_row_without_resolvable_parcel() -> None:
    row = to_zba_row(ZbaRecord(appealnumber="99", opa_account_num=None, decision="GRANTED"))
    assert row is not None
    assert row["parcel_number"] is None


def test_to_zba_row_drops_row_without_appeal_number() -> None:
    assert to_zba_row(ZbaRecord(appealnumber=None, decision="GRANTED")) is None


def test_to_zba_row_falls_back_to_scheduled_date() -> None:
    row = to_zba_row(
        ZbaRecord(appealnumber="1", decisiondate=None, scheduleddate="2020-05-01T00:00:00Z")
    )
    assert row is not None
    assert row["decision_date"] == date(2020, 5, 1)
