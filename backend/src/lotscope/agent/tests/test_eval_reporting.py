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


def test_a_subset_run_does_not_report_the_rest_as_removed() -> None:
    """A pull request runs ten of forty tasks. The thirty it skipped are not regressions."""
    full = baseline.snapshot([_result(f"t{i}") for i in range(40)], model="m")
    subset = baseline.snapshot([_result(f"t{i}") for i in range(10)], model="m")

    assert baseline.compare(full, subset) == []
    report = baseline.report(full, subset)
    assert "removed" not in report
    assert "30 task(s) in the baseline were not run" in report
    assert "10 tasks run" in report


def test_a_regression_inside_a_subset_is_still_reported() -> None:
    full = baseline.snapshot([_result(f"t{i}") for i in range(40)], model="m")
    subset = baseline.snapshot(
        [_result("t0", passed=False), *[_result(f"t{i}") for i in range(1, 10)]], model="m"
    )

    deltas = baseline.compare(full, subset)
    assert [d.task_id for d in deltas] == ["t0"]
    assert "100% -> 90%" in baseline.report(full, subset)


def test_a_task_added_since_the_baseline_is_named_as_new() -> None:
    old = baseline.snapshot([_result("t0")], model="m")
    new = baseline.snapshot([_result("t0"), _result("t1")], model="m")

    deltas = baseline.compare(old, new)
    assert [(d.task_id, d.detail) for d in deltas] == [("t1", "new task")]


def test_a_task_the_cap_cut_off_is_distinguishable_from_one_deliberately_not_run() -> None:
    """The nightly cap truncating the suite is a failure; --no-mutate skipping is not."""
    from lotscope.agent.evals.runner import CAP_REACHED, TaskResult

    cut_off = TaskResult(
        task_id="a",
        question="q",
        answer="",
        tools_called=[],
        skipped=True,
        error=CAP_REACHED.format(cap=5.0),
    )
    by_choice = TaskResult(
        task_id="b",
        question="q",
        answer="",
        tools_called=[],
        skipped=True,
        error="not run: edits stored data, so it is local-only",
    )

    marker = CAP_REACHED.split("$")[0]
    assert marker in (cut_off.error or "")
    assert marker not in (by_choice.error or "")
    # Neither is graded, and neither counts as an error.
    assert cut_off.errored is False
    assert by_choice.errored is False
