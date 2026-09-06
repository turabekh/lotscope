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
        "rebuild_screen_index",
        "recompute_distress",
        "recompute_assemblage",
        "recompute_buyers",
        "send_daily_packet_emails",
        "send_sheriff_change_emails",
        "send_daily_digests",
        "send_weekly_digests",
        "send_deal_reminder_emails",
        "send_sales_week_emails",
        "snapshot_stats",
        "reconcile_upstream_sample",
        "send_ops_health_digest",
        "send_ops_alerts",
        "build_daily_signals",
        "send_morning_briefs",
        "summarise_conversations",
        "send_error_digest_email",
    }


async def test_the_nightly_job_rebuilds_the_screening_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake(session_factory: object) -> int:
        captured["called"] = True
        return 9

    monkeypatch.setattr(worker, "rebuild_all_screens", fake)
    result = await worker.rebuild_screen_index({"session_factory": object()})

    assert result == 9
    assert captured["called"] is True
