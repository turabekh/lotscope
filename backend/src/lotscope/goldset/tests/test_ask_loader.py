import json
from pathlib import Path

import pytest

from lotscope.goldset.ask_loader import (
    DEFAULT_ASK_SET,
    AskSetError,
    load_ask_cases,
    shared_cases,
)


def _write(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def _case(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "question_id": "q1",
        "question": "what is the minimum lot area?",
        "parcel_number": "phl:1",
        "category": "district_dimensional",
        "coverage": "shared",
        "primary_cites": ["14-701"],
    }
    base.update(overrides)
    return base


def test_a_case_round_trips_from_the_file(tmp_path: Path) -> None:
    cases = load_ask_cases(_write(tmp_path, [_case()]))

    assert [case.question_id for case in cases] == ["q1"]
    assert cases[0].primary_cites == ["14-701"]


def test_an_answerable_case_without_ground_truth_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AskSetError, match="no primary cite"):
        load_ask_cases(_write(tmp_path, [_case(primary_cites=[])]))


def test_a_refusal_case_that_names_a_cite_is_rejected(tmp_path: Path) -> None:
    rows = [_case(coverage="out_of_corpus", category="out_of_corpus")]
    with pytest.raises(AskSetError, match="expects a refusal"):
        load_ask_cases(_write(tmp_path, rows))


def test_a_repeated_question_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(AskSetError, match="repeats question_id"):
        load_ask_cases(_write(tmp_path, [_case(), _case()]))


def test_comments_and_blank_lines_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(f"# a note\n\n{json.dumps(_case())}\n", encoding="utf-8")

    assert len(load_ask_cases(path)) == 1


def test_the_shared_subset_is_the_fair_fight(tmp_path: Path) -> None:
    rows = [
        _case(question_id="a", coverage="shared"),
        _case(question_id="b", coverage="phillycode_only"),
    ]

    assert [case.question_id for case in shared_cases(load_ask_cases(_write(tmp_path, rows)))] == [
        "a"
    ]


def test_the_shipped_set_parses() -> None:
    assert load_ask_cases(DEFAULT_ASK_SET)
