from datetime import UTC, datetime
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from lotscope.assemblage.jobs import recompute_all_assemblage
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.distress.jobs import recompute_all_distress
from lotscope.ingestion.jobs import INGEST_JOBS
from lotscope.ingestion.retention import sweep_retention
from lotscope.notifications.email import get_email_sender
from lotscope.notifications.push import get_push_sender
from lotscope.notifications.service import (
    send_digests,
    send_feed_digests,
    send_push_alerts,
    send_saved_search_alerts,
)
from lotscope.skiptrace.jobs import grant_investor_credits
from lotscope.vacancy.jobs import recompute_all_vacancy_confidence
from lotscope.verdict.jobs import recompute_all_verdicts

_logger = get_logger("worker")


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    ctx["settings"] = settings
    ctx["engine"] = engine
    ctx["session_factory"] = create_session_factory(engine)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


async def ingest_dataset(ctx: dict[str, Any], name: str) -> int:
    rows = await INGEST_JOBS[name](ctx["session_factory"], ctx["settings"])
    _logger.info("dataset_ingested", dataset=name, rows=rows)
    return rows


async def ingest_all(ctx: dict[str, Any]) -> int:
    total = 0
    for name in INGEST_JOBS:
        total += await ingest_dataset(ctx, name)
    return total


async def sweep_ingestion_retention(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    async with ctx["session_factory"]() as session:
        result = await sweep_retention(
            session,
            raw_retention_days=settings.raw_retention_days,
            event_retention_months=settings.event_retention_months,
        )
        await session.commit()
    _logger.info(
        "swept_ingestion_retention",
        raw_deleted=result.raw_deleted,
        events_deleted=result.events_deleted,
    )
    return result.raw_deleted + result.events_deleted


async def recompute_verdicts(ctx: dict[str, Any]) -> int:
    count = await recompute_all_verdicts(ctx["session_factory"])
    _logger.info("recomputed_verdicts", count=count)
    return count


async def recompute_vacant_verdicts(ctx: dict[str, Any]) -> int:
    count = await recompute_all_verdicts(ctx["session_factory"], vacant_only=True)
    _logger.info("recomputed_vacant_verdicts", count=count)
    return count


async def recompute_distress(ctx: dict[str, Any]) -> int:
    count = await recompute_all_distress(ctx["session_factory"])
    _logger.info("recomputed_distress", count=count)
    return count


async def recompute_assemblage(ctx: dict[str, Any]) -> int:
    count = await recompute_all_assemblage(ctx["session_factory"])
    _logger.info("recomputed_assemblage", plays=count)
    return count


async def recompute_vacancy_confidence(ctx: dict[str, Any]) -> int:
    count = await recompute_all_vacancy_confidence(ctx["session_factory"])
    _logger.info("recomputed_vacancy_confidence", count=count)
    return count


async def grant_investor_skiptrace_credits(ctx: dict[str, Any]) -> int:
    month = datetime.now(UTC).strftime("%Y-%m")
    count = await grant_investor_credits(ctx["session_factory"], month=month)
    _logger.info("granted_investor_credits", count=count, month=month)
    return count


async def send_weekly_digests(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    return await send_digests(ctx["session_factory"], sender, settings, frequency="weekly")


async def send_daily_digests(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    return await send_digests(ctx["session_factory"], sender, settings, frequency="daily")


async def send_push_notifications(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_push_sender(settings)
    return await send_push_alerts(ctx["session_factory"], sender, settings)


async def send_saved_search_match_alerts(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_saved_search_alerts(ctx["session_factory"], sender, settings)
    _logger.info("sent_saved_search_alerts", count=count)
    return count


async def send_feed_digest_emails(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_feed_digests(ctx["session_factory"], sender, settings)
    _logger.info("sent_feed_digests", count=count)
    return count


class WorkerSettings:
    functions: ClassVar = [
        ingest_dataset,
        ingest_all,
        sweep_ingestion_retention,
        recompute_verdicts,
        recompute_vacant_verdicts,
        recompute_distress,
        recompute_assemblage,
        recompute_vacancy_confidence,
        grant_investor_skiptrace_credits,
        send_weekly_digests,
        send_daily_digests,
        send_push_notifications,
        send_saved_search_match_alerts,
        send_feed_digest_emails,
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs: ClassVar = [
        cron(sweep_ingestion_retention, hour=2, minute=0),
        cron(ingest_all, hour=4, minute=0),
        cron(recompute_vacancy_confidence, hour=6, minute=30),
        cron(recompute_vacant_verdicts, hour=7, minute=0),
        cron(recompute_distress, hour=8, minute=0),
        cron(recompute_assemblage, hour=8, minute=30),
        cron(grant_investor_skiptrace_credits, day=1, hour=5, minute=0),
        cron(recompute_verdicts, weekday="sun", hour=5, minute=0),
        cron(send_push_notifications, hour=12, minute=0),
        cron(send_daily_digests, hour=13, minute=0),
        cron(send_weekly_digests, weekday="mon", hour=13, minute=30),
        cron(send_saved_search_match_alerts, hour=9, minute=0),
        cron(send_feed_digest_emails, hour=13, minute=15),
    ]
