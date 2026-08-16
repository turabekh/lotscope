from lotscope.worker import (
    BULK_JOB_TIMEOUT,
    DEFAULT_JOB_TIMEOUT,
    INGEST_JOB_TIMEOUT,
    WorkerSettings,
)

ARQ_DEFAULT_JOB_TIMEOUT = 300


def _timeout_by_name() -> dict[str, float | None]:
    timeouts: dict[str, float | None] = {}
    for entry in WorkerSettings.functions:
        name = getattr(entry, "name", None) or getattr(entry, "__name__", repr(entry))
        timeouts[str(name)] = getattr(entry, "timeout_s", None)
    return timeouts


def test_long_running_jobs_are_not_left_on_the_arq_default() -> None:
    timeouts = _timeout_by_name()

    for name in ("ingest_all", "ingest_dataset"):
        assert timeouts[name] == INGEST_JOB_TIMEOUT
    for name in (
        "recompute_verdicts",
        "recompute_vacant_verdicts",
        "recompute_distress",
        "recompute_assemblage",
        "recompute_vacancy_confidence",
    ):
        assert timeouts[name] == BULK_JOB_TIMEOUT


def test_every_bulk_timeout_clears_the_arq_default_that_killed_ingestion() -> None:
    assert WorkerSettings.job_timeout == DEFAULT_JOB_TIMEOUT
    assert DEFAULT_JOB_TIMEOUT > ARQ_DEFAULT_JOB_TIMEOUT
    assert INGEST_JOB_TIMEOUT > DEFAULT_JOB_TIMEOUT
    assert BULK_JOB_TIMEOUT > INGEST_JOB_TIMEOUT
