from lotscope.ops.reconcile import (
    FIELD_PAIRS,
    FieldPair,
    ReconciliationReport,
    compare_rows,
    upstream_query,
)


def _stored(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "parcel_number": "phl:012345678",
        "owner": "ARCH STREET PRESBYTERIAN",
        "address": "1724 ARCH ST",
        "base_zoning_code": "CMX5",
        "market_value": 1_680_900.0,
        "lot_area_sqft": 3234.0,
    }
    row.update(overrides)
    return row


def _upstream(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "parcel_number": "012345678",
        "owner_1": "ARCH STREET PRESBYTERIAN",
        "location": "1724 ARCH ST",
        "zoning": "CMX5",
        "market_value": 1_680_900.0,
        "total_area": 3234.0,
    }
    row.update(overrides)
    return row


def test_an_agreeing_parcel_reports_no_drift() -> None:
    assert compare_rows(_stored(), _upstream()) == []


def test_a_changed_owner_is_reported() -> None:
    drift = compare_rows(_stored(), _upstream(owner_1="NEW OWNER LLC"))

    assert [item.field for item in drift] == ["owner"]
    assert drift[0].stored == "ARCH STREET PRESBYTERIAN"
    assert drift[0].upstream == "NEW OWNER LLC"


def test_whitespace_and_case_do_not_count_as_drift() -> None:
    assert compare_rows(_stored(), _upstream(owner_1="  arch   street presbyterian ")) == []


def test_a_reassessment_is_reported() -> None:
    drift = compare_rows(_stored(), _upstream(market_value=2_000_000.0))

    assert [item.field for item in drift] == ["market_value"]


def test_rounding_noise_is_not_reported_as_drift() -> None:
    assert compare_rows(_stored(), _upstream(market_value=1_680_900.004)) == []


def test_a_missing_upstream_value_is_drift_not_agreement() -> None:
    drift = compare_rows(_stored(), _upstream(zoning=None))

    assert [item.field for item in drift] == ["base_zoning_code"]
    assert drift[0].upstream is None


def test_every_pair_can_drift_independently() -> None:
    drift = compare_rows(
        _stored(),
        _upstream(owner_1="X", location="Y", zoning="Z", market_value=1.0, total_area=2.0),
    )

    assert {item.field for item in drift} == {pair.stored_column for pair in FIELD_PAIRS}


def test_the_upstream_query_asks_only_for_the_sampled_parcels() -> None:
    sql = upstream_query(["012345678", "987654321"])

    assert "opa_properties_public" in sql
    assert "'012345678'" in sql
    assert "'987654321'" in sql
    for pair in FIELD_PAIRS:
        assert pair.upstream_column in sql


def test_a_parcel_number_carrying_a_quote_cannot_break_out_of_the_query() -> None:
    sql = upstream_query(["123'; DROP TABLE parcel;--"])

    assert "'123''; DROP TABLE parcel;--'" in sql


def test_agreement_counts_parcels_not_fields() -> None:
    report = ReconciliationReport(sampled=10, compared=10)
    report.drifted.extend(compare_rows(_stored(), _upstream(owner_1="A", location="B")))

    assert len(report.drifted) == 2
    assert len(report.drifted_parcels) == 1
    assert report.agreement == 0.9


def test_a_custom_pair_set_is_honoured() -> None:
    pairs = (FieldPair("owner", "owner_1"),)

    assert compare_rows(_stored(), _upstream(market_value=99.0), pairs) == []
