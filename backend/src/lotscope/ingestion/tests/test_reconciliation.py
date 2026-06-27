from lotscope.ingestion.reconciliation import (
    SourceRecord,
    canonical_parcel_number,
    normalize_account,
    reconcile,
)


def test_normalize_account_canonicalizes_representations() -> None:
    assert normalize_account("  123456789 ") == "123456789"
    assert normalize_account("123-456-789") == "123456789"
    assert normalize_account(12345) == "000012345"
    assert normalize_account("1234567") == "001234567"


def test_normalize_account_rejects_unusable_values() -> None:
    assert normalize_account(None) is None
    assert normalize_account("") is None
    assert normalize_account("abc") is None
    assert normalize_account("1234567890") is None


def test_canonical_prefers_opa_then_brt() -> None:
    assert canonical_parcel_number(SourceRecord("opa", opa_account="1234567")) == "001234567"
    assert canonical_parcel_number(SourceRecord("pwd", brt_number="1234567")) == "001234567"


def test_reconcile_merges_sources_to_one_canonical_parcel() -> None:
    result = reconcile(
        [
            SourceRecord("opa", opa_account="001234567"),
            SourceRecord("pwd", brt_number="1234567", pwd_parcel_id="pwd-9"),
            SourceRecord("rtt", opa_account="1234567"),
        ]
    )
    assert len(result.parcels) == 1
    parcel = result.parcels[0]
    assert parcel.parcel_number == "001234567"
    assert parcel.pwd_parcel_id == "PWD-9"
    assert parcel.brt_number == "001234567"
    assert parcel.sources == ["opa", "pwd", "rtt"]
    assert result.unresolved == []


def test_reconcile_reports_unresolvable_records() -> None:
    bad = SourceRecord("rtt", opa_account=None, brt_number="not-a-number")
    result = reconcile([bad])
    assert result.parcels == []
    assert result.unresolved == [bad]
