import pytest

from lotscope.ingestion.loaders.hbg_violations import (
    ViolationFieldMap,
    _normalize_status,
    map_violation_row,
)

FIELD_MAP = ViolationFieldMap(
    parcel_id="Parcel",
    external_id="CaseNo",
    violation_type="Violation",
    status="Status",
    opened="DateOpened",
    closed="DateClosed",
)


def test_map_violation_row_normalizes_key_and_fields() -> None:
    row = {
        "Parcel": "04-038-028",
        "CaseNo": "CE-2026-1234",
        "Violation": "High grass and weeds",
        "Status": "Open",
        "DateOpened": "03/14/2026",
        "DateClosed": "",
    }
    mapped = map_violation_row(row, FIELD_MAP)
    assert mapped is not None
    assert mapped["parcel_number"] == "hbg:04-038-028"
    assert mapped["external_id"] == "CE-2026-1234"
    assert mapped["event_type"] == "violation"
    assert mapped["status"] == "OPEN"
    assert mapped["event_date"].isoformat() == "2026-03-14"
    assert mapped["description"] == "High grass and weeds"


def test_map_violation_row_skips_without_parcel_or_case() -> None:
    assert map_violation_row({"CaseNo": "X", "Parcel": ""}, FIELD_MAP) is None
    assert map_violation_row({"Parcel": "04-038-028", "CaseNo": ""}, FIELD_MAP) is None


def test_status_normalization_maps_synonyms() -> None:
    assert _normalize_status("Complied") == "CLOSED"
    assert _normalize_status("Outstanding") == "OPEN"
    assert _normalize_status("Referred to court") == "REFERRED TO COURT"


def test_rtkl_note_appears_only_when_filed(monkeypatch: pytest.MonkeyPatch) -> None:
    from lotscope.markets import capabilities

    base = capabilities.checklist_state_detail("hbg", "li", "no_data_source")
    assert "Right-to-Know" not in base
    monkeypatch.setattr(capabilities, "_RTKL_FILED", frozenset({("hbg", "li")}))
    filed = capabilities.checklist_state_detail("hbg", "li", "no_data_source")
    assert "Right-to-Know" in filed
