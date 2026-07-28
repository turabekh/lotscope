import json
from pathlib import Path

import pytest

from lotscope.goldset.loader import GoldSetError, load_cases
from lotscope.goldset.logic import compare_case
from lotscope.goldset.schemas import ExpectedFacts, GoldCase

_SAMPLE = Path(__file__).resolve().parents[4] / "data" / "goldset" / "phl-sample.jsonl"


def _case(**kw: object) -> dict[str, object]:
    base: dict[str, object] = {
        "parcel_number": "phl:1",
        "categories": ["standard_rsa_rowhouse"],
        "expected": {"district_code": "RSA-5"},
    }
    base.update(kw)
    return base


def test_a_case_cannot_claim_review_without_a_named_reviewer() -> None:
    with pytest.raises(ValueError, match="never inferred"):
        GoldCase.model_validate(_case(review_status="reviewed"))


def test_a_reviewed_case_must_record_when_it_was_reviewed() -> None:
    with pytest.raises(ValueError, match="date it was reviewed"):
        GoldCase.model_validate(_case(review_status="reviewed", reviewer="A. Zoning RA"))


def test_a_fully_attributed_review_is_accepted() -> None:
    case = GoldCase.model_validate(
        _case(review_status="reviewed", reviewer="A. Zoning RA", reviewed_on="2026-07-28")
    )
    assert case.review_status == "reviewed"


def test_cases_default_to_unreviewed() -> None:
    assert GoldCase.model_validate(_case()).review_status == "unreviewed"


def test_a_wrong_district_is_critical() -> None:
    found = compare_case("phl:1", ExpectedFacts(district_code="RSA-5"), {"district_code": "RSA-3"})
    assert [(d.field_name, d.severity) for d in found] == [("district_code", "critical")]


def test_a_wrong_unit_conclusion_is_critical() -> None:
    found = compare_case("phl:1", ExpectedFacts(by_right_units=1), {"by_right_units": 3})
    assert found[0].severity == "critical"


def test_a_missed_master_plan_requirement_is_critical() -> None:
    found = compare_case(
        "phl:1", ExpectedFacts(requires_master_plan=True), {"requires_master_plan": False}
    )
    assert found[0].field_name == "requires_master_plan"
    assert found[0].severity == "critical"


def test_a_missing_risk_flag_is_material_not_critical() -> None:
    found = compare_case(
        "phl:1", ExpectedFacts(expected_risk_flags=["flood_zone"]), {"risk_flag_codes": []}
    )
    assert found[0].severity == "material"


def test_unstated_expectations_are_not_compared() -> None:
    assert compare_case("phl:1", ExpectedFacts(), {"district_code": "RSA-3"}) == []


def test_a_matching_case_reports_nothing() -> None:
    found = compare_case(
        "phl:1",
        ExpectedFacts(district_code="RSA-5", by_right_units=1, can_build_by_right=True),
        {"district_code": "RSA-5", "by_right_units": 1, "can_build_by_right": True},
    )
    assert found == []


def test_the_sample_file_loads_and_demonstrates_the_workflow() -> None:
    cases = load_cases(_SAMPLE)
    assert len(cases) >= 3
    assert all(case.review_status == "unreviewed" for case in cases)
    assert all(case.evidence_refs for case in cases)


def test_duplicate_parcels_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dupes.jsonl"
    path.write_text("\n".join([json.dumps(_case()), json.dumps(_case())]), encoding="utf-8")
    with pytest.raises(GoldSetError, match="repeats parcel"):
        load_cases(path)


def test_a_malformed_line_names_the_line_number(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(_case()) + "\n{not json}\n", encoding="utf-8")
    with pytest.raises(GoldSetError, match=":2 "):
        load_cases(path)
