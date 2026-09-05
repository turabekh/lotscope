"""A recorded eval run, so a change in behaviour is visible instead of remembered.

The baseline holds the tool sequence and per-assertion result for every task. Comparing
against it answers the question a pass rate cannot: which task changed, and did it start
calling a different tool.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASELINE_PATH = Path(__file__).with_name("baseline.json")


@dataclass(frozen=True)
class Delta:
    task_id: str
    was: str
    now: str
    detail: str


def snapshot(results: list[Any], *, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "tasks": {
            result.task_id: {
                "passed": result.passed,
                "tools": result.tools_called,
                "assertions": [
                    {"kind": a.kind, "value": a.value, "passed": a.passed}
                    for a in result.assertions
                ],
            }
            for result in results
            if not result.skipped and not getattr(result, "errored", False)
        },
    }


class BrokenRunError(Exception):
    """The run did not finish cleanly, so it is not a baseline."""


def write(results: list[Any], *, model: str, path: Path | None = None) -> Path:
    # A baseline recorded from a run that errored would encode an outage as behaviour, and
    # every later run would be compared against it.
    broken = [result.task_id for result in results if getattr(result, "errored", False)]
    if broken:
        raise BrokenRunError(
            f"{len(broken)} task(s) errored ({', '.join(broken[:5])}), so this run is not a "
            f"baseline. Fix the cause and record again."
        )
    target = path or BASELINE_PATH
    target.write_text(json.dumps(snapshot(results, model=model), indent=2, sort_keys=True) + "\n")
    return target


def read(path: Path | None = None) -> dict[str, Any] | None:
    target = path or BASELINE_PATH
    if not target.exists():
        return None
    loaded: dict[str, Any] = json.loads(target.read_text())
    return loaded


def pass_rate(snapshot_data: dict[str, Any]) -> float:
    tasks = snapshot_data.get("tasks", {})
    if not tasks:
        return 0.0
    return sum(1 for task in tasks.values() if task["passed"]) / len(tasks)


def compare(old: dict[str, Any], new: dict[str, Any]) -> list[Delta]:
    """Every task whose verdict or tool sequence moved. Order matters in a tool sequence.

    Only tasks the run actually covered are compared. A pull request runs ten of forty, and
    reporting the other thirty as "removed" would bury a real regression under thirty lines
    of noise — the same failure as a suite that skipped everything, pointed the other way.
    """
    deltas: list[Delta] = []
    old_tasks, new_tasks = old.get("tasks", {}), new.get("tasks", {})

    for task_id in sorted(new_tasks):
        before, after = old_tasks.get(task_id), new_tasks[task_id]
        if before is None:
            deltas.append(
                Delta(task_id, "absent", "pass" if after["passed"] else "fail", "new task")
            )
            continue
        if before["passed"] != after["passed"]:
            failed = [a["value"] for a in after["assertions"] if not a["passed"]]
            deltas.append(
                Delta(
                    task_id,
                    "pass" if before["passed"] else "fail",
                    "pass" if after["passed"] else "fail",
                    f"failing: {failed}" if failed else "now passing",
                )
            )
        elif before["tools"] != after["tools"]:
            deltas.append(
                Delta(
                    task_id,
                    " ".join(before["tools"]) or "none",
                    " ".join(after["tools"]) or "none",
                    "same verdict, different tools",
                )
            )
    return deltas


def report(old: dict[str, Any] | None, new: dict[str, Any]) -> str:
    lines: list[str] = []
    rate = pass_rate(new)
    if old is None:
        lines.append(f"No baseline recorded. This run: {rate:.0%} of tasks passed.")
        return "\n".join(lines)

    covered = set(new.get("tasks", {}))
    recorded = set(old.get("tasks", {}))
    # Compare like with like: a subset run's pass rate only means something against the
    # same subset of the baseline.
    shared = {k: v for k, v in old.get("tasks", {}).items() if k in covered}
    was = pass_rate({"tasks": shared}) if shared else rate
    arrow = "no change" if abs(rate - was) < 1e-9 else f"{was:.0%} -> {rate:.0%}"
    lines.append(f"Pass rate {arrow} ({len(covered)} tasks run).")

    not_run = recorded - covered
    if not_run:
        lines.append(f"{len(not_run)} task(s) in the baseline were not run and are not compared.")

    deltas = compare(old, new)
    if not deltas:
        lines.append("Every task behaved exactly as the baseline recorded.")
        return "\n".join(lines)

    lines.append("")
    for delta in deltas:
        lines.append(f"- {delta.task_id}: {delta.was} -> {delta.now} ({delta.detail})")
    return "\n".join(lines)
