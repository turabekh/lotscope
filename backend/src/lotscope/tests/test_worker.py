from typing import Any

import pytest

from lotscope import worker


def _cron_names() -> set[str]:
    return {job.coroutine.__qualname__ for job in worker.WorkerSettings.cron_jobs}


def test_scheduled_jobs_cover_ingest_recomputes_and_digests() -> None:
    assert _cron_names() == {
        "sweep_ingestion_retention",
        "ingest_all",
        "recompute_vacancy_confidence",
        "recompute_vacant_verdicts",
        "recompute_verdicts",
        "recompute_distress",
        "recompute_assemblage",
        "grant_investor_skiptrace_credits",
        "grant_investor_packet_credits",
        "send_daily_digests",
        "send_weekly_digests",
        "send_push_notifications",
        "send_saved_search_match_alerts",
        "send_feed_digest_emails",
    }


async def test_recompute_vacant_verdicts_requests_vacant_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake(session_factory: object, *, vacant_only: bool = False) -> int:
        captured["vacant_only"] = vacant_only
        return 9

    monkeypatch.setattr(worker, "recompute_all_verdicts", fake)
    result = await worker.recompute_vacant_verdicts({"session_factory": object()})

    assert result == 9
    assert captured["vacant_only"] is True


async def test_recompute_verdicts_runs_full(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake(session_factory: object, *, vacant_only: bool = False) -> int:
        captured["vacant_only"] = vacant_only
        return 4

    monkeypatch.setattr(worker, "recompute_all_verdicts", fake)
    result = await worker.recompute_verdicts({"session_factory": object()})

    assert result == 4
    assert captured["vacant_only"] is False
