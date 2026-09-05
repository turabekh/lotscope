"""An outage is not a behaviour regression, and a broken run is not a baseline."""

import pytest

from lotscope.agent.evals import baseline
from lotscope.agent.evals.runner import AssertionResult, TaskResult


def _result(task_id: str, *, error: str | None = None, passed: bool = True) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        question="q",
        answer="" if error else "an answer",
        tools_called=["get_parcel"],
        assertions=[]
        if error
        else [AssertionResult(kind="contains", value="x", passed=passed, why="")],
        error=error,
    )


def test_a_task_that_errored_is_not_counted_as_a_failure() -> None:
    errored = _result("boom", error="credit balance is too low")
    assert errored.errored is True
    assert errored.passed is False
    assert errored.assertions == []


def test_a_graded_failure_is_not_an_error() -> None:
    failed = _result("wrong", passed=False)
    assert failed.errored is False
    assert failed.passed is False


def test_a_run_with_an_error_is_refused_as_a_baseline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    results = [_result("ok"), _result("boom", error="credit balance is too low")]
    with pytest.raises(baseline.BrokenRunError, match="boom"):
        baseline.write(results, model="m", path=tmp_path / "baseline.json")
    assert not (tmp_path / "baseline.json").exists()


def test_a_clean_run_records_tools_and_assertions(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = baseline.write([_result("ok")], model="m", path=tmp_path / "baseline.json")
    stored = baseline.read(path)
    assert stored is not None
    assert stored["tasks"]["ok"]["tools"] == ["get_parcel"]
    assert baseline.pass_rate(stored) == 1.0


def test_the_delta_names_the_task_that_changed_and_why() -> None:
    old = baseline.snapshot([_result("a"), _result("b")], model="m")
    new = baseline.snapshot([_result("a"), _result("b", passed=False)], model="m")
    deltas = baseline.compare(old, new)
    assert [d.task_id for d in deltas] == ["b"]
    assert deltas[0].was == "pass"
    assert deltas[0].now == "fail"


def test_a_changed_tool_sequence_is_a_delta_even_when_the_verdict_holds() -> None:
    old = baseline.snapshot([_result("a")], model="m")
    changed = _result("a")
    changed.tools_called = ["live_opa"]
    deltas = baseline.compare(old, baseline.snapshot([changed], model="m"))
    assert deltas[0].detail == "same verdict, different tools"
