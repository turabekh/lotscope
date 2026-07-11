from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.admin.catalog import (
    CATALOG_BY_ID,
    INGEST_KIND,
    MAINTENANCE_KIND,
    RECOMPUTE_KIND,
    parse_params,
)
from lotscope.admin.service import mark_job_finished, mark_job_running
from lotscope.appeal.jobs import grant_investor_appeal_packets
from lotscope.assemblage.jobs import recompute_all_assemblage
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.errors import NotFoundError
from lotscope.core.logging import configure_logging, get_logger
from lotscope.distress.jobs import recompute_all_distress
from lotscope.ingestion.jobs import INGEST_JOBS, PARAM_INGEST_JOBS, ingest_market, markets
from lotscope.ingestion.retention import sweep_retention
from lotscope.notifications.email import get_email_sender
from lotscope.notifications.push import get_push_sender
from lotscope.notifications.service import (
    send_deal_reminders,
    send_digests,
    send_feed_digests,
    send_push_alerts,
    send_sales_week_digest,
    send_saved_search_alerts,
)
from lotscope.ops.alerts import send_ops_digest, send_ops_failure_alerts
from lotscope.ops.gates import seed_market_gates
from lotscope.ops.stats import snapshot_market_stats
from lotscope.skiptrace.jobs import grant_investor_credits
from lotscope.vacancy.jobs import recompute_all_vacancy_confidence
from lotscope.verdict.jobs import recompute_all_verdicts
from lotscope.zoning.seed import seed_zoning_standards
from lotscope.zoning.seed_hbg import seed_hbg_zoning_standards
from lotscope.zoning.seed_pgh import seed_pgh_zoning_standards

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


async def ingest_dataset(ctx: dict[str, Any], market: str, name: str) -> int:
    rows = await INGEST_JOBS[(market, name)](ctx["session_factory"], ctx["settings"])
    _logger.info("dataset_ingested", market=market, dataset=name, rows=rows)
    return rows


async def ingest_all(ctx: dict[str, Any]) -> int:
    total = 0
    for market in markets():
        total += await ingest_market(ctx["session_factory"], ctx["settings"], market)
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


async def snapshot_stats(ctx: dict[str, Any]) -> int:
    count = await snapshot_market_stats(ctx["session_factory"])
    _logger.info("snapshotted_market_stats", markets=count)
    return count


_RecomputeFn = Callable[[async_sessionmaker[AsyncSession]], Awaitable[int]]

_RECOMPUTE_DISPATCH: dict[str, _RecomputeFn] = {
    "recompute:verdicts": recompute_all_verdicts,
    "recompute:vacant_verdicts": lambda factory: recompute_all_verdicts(factory, vacant_only=True),
    "recompute:distress": recompute_all_distress,
    "recompute:vacancy": recompute_all_vacancy_confidence,
    "recompute:assemblage": recompute_all_assemblage,
}


async def _seed_zoning_standards(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        total = await seed_zoning_standards(session)
        total += await seed_hbg_zoning_standards(session)
        total += await seed_pgh_zoning_standards(session)
        await session.commit()
    return total


async def _seed_market_gates(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        total = await seed_market_gates(session)
        await session.commit()
    return total


_MAINTENANCE_DISPATCH: dict[str, _RecomputeFn] = {
    "maintenance:seed_zoning": _seed_zoning_standards,
    "maintenance:snapshot_stats": snapshot_market_stats,
    "maintenance:seed_gates": _seed_market_gates,
}


async def _dispatch_admin_job(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Any,
    job_id: str,
    params: dict[str, str],
) -> int:
    spec = CATALOG_BY_ID.get(job_id)
    if spec is None:
        raise NotFoundError(f"Job {job_id!r} is not in the catalog.")
    if spec.kind == INGEST_KIND:
        if spec.market is None or spec.dataset is None:
            raise NotFoundError(f"Job {job_id!r} is missing ingest coordinates.")
        key = (spec.market, spec.dataset)
        if key in PARAM_INGEST_JOBS:
            return await PARAM_INGEST_JOBS[key](
                session_factory, settings, **parse_params(spec, params)
            )
        return await INGEST_JOBS[key](session_factory, settings)
    if spec.kind == RECOMPUTE_KIND:
        return await _RECOMPUTE_DISPATCH[spec.id](session_factory)
    if spec.kind == MAINTENANCE_KIND:
        return await _MAINTENANCE_DISPATCH[spec.id](session_factory)
    raise NotFoundError(f"Job {job_id!r} has an unsupported kind {spec.kind!r}.")


async def run_admin_job(ctx: dict[str, Any], job_run_id: int) -> int:
    session_factory = ctx["session_factory"]
    async with session_factory() as session:
        run = await mark_job_running(session, job_run_id)
        job_id = run.job_id
        params = dict(run.params or {})
        await session.commit()
    try:
        rows = await _dispatch_admin_job(session_factory, ctx["settings"], job_id, params)
    except Exception as error:
        async with session_factory() as session:
            await mark_job_finished(session, job_run_id, status="failed", error=str(error))
            await session.commit()
        _logger.error("admin_job_failed", job_id=job_id, error=str(error))
        return 0
    async with session_factory() as session:
        await mark_job_finished(session, job_run_id, status="success", result_count=rows)
        await session.commit()
    _logger.info("admin_job_finished", job_id=job_id, rows=rows)
    return rows


async def grant_investor_skiptrace_credits(ctx: dict[str, Any]) -> int:
    month = datetime.now(UTC).strftime("%Y-%m")
    count = await grant_investor_credits(ctx["session_factory"], month=month)
    _logger.info("granted_investor_credits", count=count, month=month)
    return count


async def grant_investor_packet_credits(ctx: dict[str, Any]) -> int:
    month = datetime.now(UTC).strftime("%Y-%m")
    count = await grant_investor_appeal_packets(ctx["session_factory"], month=month)
    _logger.info("granted_investor_packets", count=count, month=month)
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


async def send_deal_reminder_emails(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_deal_reminders(ctx["session_factory"], sender, settings)
    _logger.info("sent_deal_reminders", count=count)
    return count


async def send_sales_week_emails(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_sales_week_digest(ctx["session_factory"], sender, settings)
    _logger.info("sent_sales_week", recipients=count)
    return count


async def send_ops_health_digest(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_ops_digest(ctx["session_factory"], sender, settings)
    _logger.info("sent_ops_digest", recipients=count)
    return count


async def send_ops_alerts(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_ops_failure_alerts(ctx["session_factory"], sender, settings)
    _logger.info("sent_ops_alerts", recipients=count)
    return count


class WorkerSettings:
    functions: ClassVar = [
        ingest_dataset,
        ingest_all,
        run_admin_job,
        sweep_ingestion_retention,
        recompute_verdicts,
        recompute_vacant_verdicts,
        recompute_distress,
        recompute_assemblage,
        recompute_vacancy_confidence,
        snapshot_stats,
        grant_investor_skiptrace_credits,
        grant_investor_packet_credits,
        send_weekly_digests,
        send_daily_digests,
        send_push_notifications,
        send_saved_search_match_alerts,
        send_feed_digest_emails,
        send_deal_reminder_emails,
        send_sales_week_emails,
        send_ops_health_digest,
        send_ops_alerts,
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
        cron(snapshot_stats, hour=9, minute=30),
        cron(send_ops_alerts, hour=5, minute=30),
        cron(send_ops_health_digest, hour=10, minute=0),
        cron(send_sales_week_emails, weekday="mon", hour=8, minute=0),
        cron(grant_investor_skiptrace_credits, day=1, hour=5, minute=0),
        cron(grant_investor_packet_credits, day=1, hour=5, minute=10),
        cron(recompute_verdicts, weekday="sun", hour=5, minute=0),
        cron(send_push_notifications, hour=12, minute=0),
        cron(send_daily_digests, hour=13, minute=0),
        cron(send_weekly_digests, weekday="mon", hour=13, minute=30),
        cron(send_saved_search_match_alerts, hour=9, minute=0),
        cron(send_feed_digest_emails, hour=13, minute=15),
        cron(send_deal_reminder_emails, hour=13, minute=45),
    ]
