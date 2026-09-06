from arq.cron import CronJob
from arq.worker import Function

from lotscope.worker import DEFAULT_JOB_TIMEOUT, WorkerSettings


def _declared_timeouts() -> dict[str, float]:
    return {
        entry.name: entry.timeout_s
        for entry in WorkerSettings.functions
        if isinstance(entry, Function) and entry.timeout_s is not None
    }


_CRON_PREFIX = "cron:"


def _cron_timeouts() -> dict[str, float | None]:
    return {
        entry.name.removeprefix(_CRON_PREFIX): entry.timeout_s
        for entry in WorkerSettings.cron_jobs
        if isinstance(entry, CronJob)
    }


def test_a_scheduled_job_keeps_the_timeout_its_function_declares() -> None:
    declared = _declared_timeouts()
    scheduled = _cron_timeouts()

    drifted = {
        name: {"cron": scheduled[name], "declared": timeout}
        for name, timeout in declared.items()
        if name in scheduled and scheduled[name] != timeout
    }

    assert drifted == {}, (
        "arq resolves a cron job's timeout from the cron() entry, not from the func() "
        "registration, so a job declared with a long timeout is still killed at the worker "
        "default when it runs on its schedule:\n  " + repr(drifted)
    )


def test_no_long_running_job_is_scheduled_under_the_worker_default() -> None:
    declared = _declared_timeouts()
    scheduled = _cron_timeouts()

    under_default = sorted(
        name
        for name, timeout in scheduled.items()
        if name in declared
        and declared[name] > DEFAULT_JOB_TIMEOUT
        and (timeout is None or timeout <= DEFAULT_JOB_TIMEOUT)
    )

    assert under_default == []


def test_the_two_registries_are_actually_compared() -> None:
    shared = set(_declared_timeouts()) & set(_cron_timeouts())

    assert "ingest_all" in shared
    assert "rebuild_screen_index" in shared
