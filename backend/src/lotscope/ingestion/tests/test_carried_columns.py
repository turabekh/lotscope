"""Every column each Philadelphia loader carries, asserted by value.

The mappers are where an upstream field becomes a field of ours, and a column that is
silently dropped or quietly renamed is a whole class of fact going missing without
anything failing. Each test maps a fully populated record and compares the whole
dictionary, so a new column that nobody asserted fails here rather than shipping unread.
"""

from datetime import date

from lotscope.ingestion.loaders.li import (
    LI_DEMOLITIONS_DATASET,
    LI_PERMITS_DATASET,
    LI_VIOLATIONS_DATASET,
    DemolitionRecord,
    PermitRecord,
    ViolationRecord,
    to_demolition_event_row,
    to_permit_event_row,
    to_violation_event_row,
)
from lotscope.ingestion.loaders.opa import OPA_DATASET, OpaRecord, to_parcel_row
from lotscope.ingestion.loaders.rtt import RTT_DATASET, RttRecord, to_sale_row
from lotscope.ingestion.loaders.sheriff import (
    SHERIFF_DATASET,
    SheriffSaleRecord,
    to_sheriff_row,
)
from lotscope.ingestion.loaders.tax import TAX_DATASET, TaxRecord, to_tax_row


def test_the_assessment_carries_every_column_it_maps() -> None:
    row = to_parcel_row(
        OpaRecord(
            parcel_number="1234567",
            location="902 S CECIL ST",
            zip_code="19143",
            owner_1="EAEAL 1300 LLC",
            mailing_street="1300 MARKET ST",
            mailing_city_state="PHILADELPHIA PA",
            mailing_zip="19107",
            category_code_description="Vacant Land",
            zoning="RSA5",
            market_value=122700.0,
            taxable_land=24540.0,
            taxable_building=98160.0,
            exempt_land=1000.0,
            exempt_building=2000.0,
            total_area=1600.0,
            frontage=16.0,
            depth=100.0,
        )
    )

    assert row == {
        "parcel_number": "phl:001234567",
        "address": "902 S CECIL ST",
        "zip_code": "19143",
        "owner": "EAEAL 1300 LLC",
        "mailing_address": "1300 MARKET ST PHILADELPHIA PA 19107",
        "land_use": "Vacant Land",
        "base_zoning_code": "RSA5",
        "market_value": 122700.0,
        "land_value": 24540.0,
        "improvement_value": 98160.0,
        "exempt_land": 1000.0,
        "exempt_building": 2000.0,
        "lot_area_sqft": 1600.0,
        "frontage_ft": 16.0,
        "depth_ft": 100.0,
        "source": OPA_DATASET,
    }


def test_a_recorded_transfer_carries_every_column_it_maps() -> None:
    row = to_sale_row(
        RttRecord(
            opa_account_num="1234567",
            street_address="902 S CECIL ST",
            document_id=" 54569271 ",
            document_type="DEED",
            recording_date="2026-06-29",
            grantors="JONES LOUIS ESTATE OF",
            grantees="EAEAL 1300 LLC",
            total_consideration=61000.0,
        )
    )

    assert row == {
        "parcel_number": "phl:001234567",
        "document_id": "54569271",
        "document_type": "DEED",
        "sale_date": date(2026, 6, 29),
        "sale_price": 61000.0,
        "grantor": "JONES LOUIS ESTATE OF",
        "grantee": "EAEAL 1300 LLC",
        "source": RTT_DATASET,
    }


def test_the_tax_snapshot_carries_every_column_it_maps() -> None:
    row = to_tax_row(
        TaxRecord(
            opa_number="1234567",
            owner="JONES LOUIS",
            year_month="202206",
            total_due=5392.54,
            principal_due=2405.33,
            num_years_owed=11,
        )
    )

    assert row == {
        "parcel_number": "phl:001234567",
        "delinquency_owner": "JONES LOUIS",
        "snapshot_period": "202206",
        "total_due": 5392.54,
        "principal_due": 2405.33,
        "years_owed": 11,
        "is_delinquent": True,
        "source": TAX_DATASET,
    }


def test_a_sheriff_listing_carries_every_column_it_maps() -> None:
    row = to_sheriff_row(
        SheriffSaleRecord(
            case_number=" 2301-1234 ",
            opa_number="1234567",
            address="902 S CECIL ST",
            sale_type="TAX",
            status="Postponed",
            sale_date="2026-09-16",
            opening_bid=1200.0,
            plaintiff="CITY OF PHILADELPHIA",
        )
    )

    assert row == {
        "parcel_number": "phl:001234567",
        "case_number": "2301-1234",
        "sale_type": "TAX",
        "status": "Postponed",
        "sale_date": date(2026, 9, 16),
        "opening_bid": 1200.0,
        "plaintiff": "CITY OF PHILADELPHIA",
        "source": SHERIFF_DATASET,
    }


def test_a_violation_carries_every_column_it_maps() -> None:
    row = to_violation_event_row(
        ViolationRecord(
            violationnumber="VI-2020-032029",
            opa_account_num="1234567",
            violationcodetitle="IMMINENTLY DANGEROUS UNSAFE STRUCTURE",
            violationstatus="OPEN",
            casestatus="IN VIOLATION",
            violationdate="2026-06-01",
        )
    )

    assert row == {
        "parcel_number": "phl:001234567",
        "external_id": "VI-2020-032029",
        "event_type": "violation",
        "source": LI_VIOLATIONS_DATASET,
        "status": "OPEN",
        "case_status": "IN VIOLATION",
        "event_date": date(2026, 6, 1),
        "description": "IMMINENTLY DANGEROUS UNSAFE STRUCTURE",
        "is_unsafe": True,
        "is_imminently_dangerous": True,
    }


def test_a_permit_carries_every_column_it_maps() -> None:
    row = to_permit_event_row(
        PermitRecord(
            permitnumber="PM-2026-001",
            opa_account_num="1234567",
            permitdescription="NEW CONSTRUCTION",
            status="COMPLETED",
            permitissuedate="2026-04-02",
        )
    )

    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["external_id"] == "PM-2026-001"
    assert row["event_type"] == "permit"
    assert row["source"] == LI_PERMITS_DATASET
    assert row["status"] == "COMPLETED"
    assert row["event_date"] == date(2026, 4, 2)
    assert row["description"] == "NEW CONSTRUCTION"


def test_a_demolition_carries_every_column_it_maps() -> None:
    row = to_demolition_event_row(
        DemolitionRecord(
            caseorpermitnumber="DM-2026-009",
            opa_account_num="1234567",
        )
    )

    assert row is not None
    assert row["parcel_number"] == "phl:001234567"
    assert row["external_id"] == "DM-2026-009"
    assert row["event_type"] == "demolition"
    assert row["source"] == LI_DEMOLITIONS_DATASET
