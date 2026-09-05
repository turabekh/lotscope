from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, ClassVar
from zoneinfo import ZoneInfo

from arq import cron, func
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.admin.catalog import (
    CATALOG_BY_ID,
    INGEST_KIND,
    MAINTENANCE_KIND,
    RECOMPUTE_KIND,
    parse_params,
)
from lotscope.admin.models import JobRun
from lotscope.admin.service import mark_job_finished, mark_job_running
from lotscope.agent.brief import build_and_brief, send_daily_briefs
from lotscope.agent.client import AnthropicToolClient
from lotscope.agent.summarise import summarise_long_conversations
from lotscope.assemblage.jobs import recompute_all_assemblage
from lotscope.buyers.jobs import recompute_all_buyers
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.errors import NotFoundError
from lotscope.core.logging import configure_logging, get_logger
from lotscope.core.market import MARKET_CODE
from lotscope.distress.jobs import recompute_all_distress
from lotscope.ingestion.carto import CartoClient
from lotscope.ingestion.jobs import INGEST_JOBS, ingest_market
from lotscope.ingestion.retention import sweep_retention
from lotscope.notifications.email import get_email_sender
from lotscope.notifications.service import (
    send_deal_reminders,
    send_digests,
    send_sales_week_digest,
    send_saved_search_alerts,
)
from lotscope.ops.alerts import send_ops_digest, send_ops_failure_alerts
from lotscope.ops.invariants import breaches, check_invariants
from lotscope.ops.reconcile import reconcile_against_opa
from lotscope.ops.stats import snapshot_market_stats
from lotscope.packet.delivery import send_daily_packets, send_sale_change_alerts
from lotscope.packet.models import SalePacket
from lotscope.packet.service import build_packet
from lotscope.vacancy.jobs import recompute_all_vacancy_confidence
from lotscope.verdict.jobs import recompute_all_verdicts
from lotscope.zoning.seed import seed_all_zoning_standards

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
    return await ingest_market(ctx["session_factory"], ctx["settings"], MARKET_CODE)


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


async def generate_sale_packet(ctx: dict[str, Any], packet_id: int) -> int:
    async with ctx["session_factory"]() as session:
        packet = await session.get(SalePacket, packet_id)
        if packet is None:
            _logger.warning("sale_packet_missing", packet_id=packet_id)
            return 0
        user_id, sale_date = packet.user_id, packet.sale_date
        try:
            built = await build_packet(session, user_id, sale_date, redis=ctx.get("redis"))
        except Exception as cause:
            await session.commit()
            _logger.error(
                "sale_packet_failed",
                packet_id=packet_id,
                error=str(cause),
                error_type=type(cause).__name__,
            )
            raise
        await session.commit()
        _logger.info("sale_packet_ready", packet_id=packet_id, path=built.pdf_path)
    return 1


PACKET_EMAIL_LOCAL_HOUR = 9
PACKET_EMAIL_TZ = ZoneInfo("America/New_York")
BRIEF_EMAIL_LOCAL_HOUR = 7


async def build_daily_signals(ctx: dict[str, Any]) -> int:
    """Runs after the ingest and the sheriff scraper, so the day's rows are all in."""
    count = await build_and_brief(ctx["session_factory"], ctx["settings"])
    _logger.info("built_daily_signals", count=count)
    return count


async def send_morning_briefs(ctx: dict[str, Any]) -> int:
    # Same shape as the packet job: cron fires on both candidate UTC hours and the local
    # clock decides, so the brief lands at 07:00 in Philadelphia on either side of DST.
    local_hour = datetime.now(PACKET_EMAIL_TZ).hour
    if local_hour != BRIEF_EMAIL_LOCAL_HOUR:
        _logger.info("briefs_skipped_off_hour", local_hour=local_hour)
        return 0
    settings = ctx["settings"]
    if not settings.anthropic_api_key:
        _logger.warning("briefs_skipped_no_model_key")
        return 0
    count = await send_daily_briefs(
        ctx["session_factory"],
        AnthropicToolClient(settings),
        get_email_sender(settings),
        settings,
    )
    _logger.info("sent_morning_briefs", count=count)
    return count


async def summarise_conversations(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    if not settings.anthropic_api_key:
        _logger.warning("summaries_skipped_no_model_key")
        return 0
    count = await summarise_long_conversations(
        ctx["session_factory"], AnthropicToolClient(settings), settings
    )
    _logger.info("summarised_conversations", memories=count)
    return count


async def send_daily_packet_emails(ctx: dict[str, Any]) -> int:
    local_hour = datetime.now(PACKET_EMAIL_TZ).hour
    if local_hour != PACKET_EMAIL_LOCAL_HOUR:
        _logger.info("packet_emails_skipped_off_hour", local_hour=local_hour)
        return 0
    settings = ctx["settings"]
    count = await send_daily_packets(ctx["session_factory"], get_email_sender(settings), settings)
    _logger.info("sent_packet_emails", count=count)
    return count


async def send_sheriff_change_emails(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    count = await send_sale_change_alerts(
        ctx["session_factory"], get_email_sender(settings), settings
    )
    _logger.info("sent_sheriff_change_emails", count=count)
    return count


async def recompute_verdicts(ctx: dict[str, Any]) -> int:
    count = await recompute_all_verdicts(ctx["session_factory"], only_stale=True)
    _logger.info("recomputed_verdicts", count=count, only_stale=True)
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


async def recompute_buyers(ctx: dict[str, Any]) -> int:
    count = await recompute_all_buyers(ctx["session_factory"])
    _logger.info("recomputed_buyers", count=count)
    return count


async def recompute_vacancy_confidence(ctx: dict[str, Any]) -> int:
    count = await recompute_all_vacancy_confidence(ctx["session_factory"])
    _logger.info("recomputed_vacancy_confidence", count=count)
    return count


async def check_verdict_invariants(ctx: dict[str, Any]) -> int:
    async with ctx["session_factory"]() as session:
        failed = breaches(await check_invariants(session, MARKET_CODE))
        for result in failed:
            _logger.error(
                "invariant_breached",
                invariant=result.invariant.name,
                violations=result.violations,
                claim=result.invariant.claim,
            )
    _logger.info("invariants_checked", breached=len(failed))
    return len(failed)


async def reconcile_upstream_sample(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    async with ctx["session_factory"]() as session, CartoClient(settings) as carto:
        report = await reconcile_against_opa(session, carto)
    if report.drifted or report.absent_upstream:
        _logger.error(
            "upstream_reconciliation_drift",
            sampled=report.sampled,
            compared=report.compared,
            agreement=round(report.agreement, 4),
            drifted_parcels=len(report.drifted_parcels),
            absent_upstream=len(report.absent_upstream),
            fields=sorted({item.field for item in report.drifted}),
        )
    else:
        _logger.info(
            "upstream_reconciliation_clean", sampled=report.sampled, compared=report.compared
        )
    return len(report.drifted_parcels)


async def snapshot_stats(ctx: dict[str, Any]) -> int:
    count = await snapshot_market_stats(ctx["session_factory"])
    _logger.info("snapshotted_market_stats", markets=count)
    return count


_RecomputeFn = Callable[[async_sessionmaker[AsyncSession], str | None], Awaitable[int]]
_MaintenanceFn = Callable[[async_sessionmaker[AsyncSession]], Awaitable[int]]

_RECOMPUTE_DISPATCH: dict[str, _RecomputeFn] = {
    "recompute:verdicts": lambda factory, market: recompute_all_verdicts(factory, market=market),
    "recompute:vacant_verdicts": lambda factory, market: recompute_all_verdicts(
        factory, vacant_only=True, market=market
    ),
    "recompute:distress": lambda factory, market: recompute_all_distress(factory, market=market),
    "recompute:vacancy": lambda factory, market: recompute_all_vacancy_confidence(
        factory, market=market
    ),
    "recompute:assemblage": lambda factory, market: recompute_all_assemblage(
        factory, market=market
    ),
    "recompute:buyers": lambda factory, market: recompute_all_buyers(factory, market=market),
}


async def _seed_zoning_standards(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        seeded = await seed_all_zoning_standards(session)
        await session.commit()
    return sum(seeded.values())


_MAINTENANCE_DISPATCH: dict[str, _MaintenanceFn] = {
    "maintenance:seed_zoning": _seed_zoning_standards,
    "maintenance:snapshot_stats": snapshot_market_stats,
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
        return await INGEST_JOBS[(spec.market, spec.dataset)](session_factory, settings)
    if spec.kind == RECOMPUTE_KIND:
        market = parse_params(spec, params).get("market")
        return await _RECOMPUTE_DISPATCH[spec.id](session_factory, market)
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


async def send_weekly_digests(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    return await send_digests(ctx["session_factory"], sender, settings, frequency="weekly")


async def send_daily_digests(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    return await send_digests(ctx["session_factory"], sender, settings, frequency="daily")


async def send_saved_search_match_alerts(ctx: dict[str, Any]) -> int:
    settings = ctx["settings"]
    sender = get_email_sender(settings)
    count = await send_saved_search_alerts(ctx["session_factory"], sender, settings)
    _logger.info("sent_saved_search_alerts", count=count)
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


_MINUTE = 60
_HOUR = 60 * _MINUTE

BULK_JOB_TIMEOUT = 36 * _HOUR
INGEST_JOB_TIMEOUT = 12 * _HOUR
DEFAULT_JOB_TIMEOUT = 30 * _MINUTE


async def _open_cron_run(
    session_factory: async_sessionmaker[AsyncSession], name: str
) -> int | None:
    try:
        async with session_factory() as session:
            run = JobRun(
                job_id=f"cron:{name}",
                label=name,
                kind="cron",
                status="running",
                started_at=datetime.now(UTC),
                triggered_by=None,
            )
            session.add(run)
            await session.commit()
            return run.id
    except Exception as exc:
        _logger.warning("cron_run_not_recorded", job=name, error=str(exc))
        return None


async def _close_cron_run(
    session_factory: async_sessionmaker[AsyncSession],
    run_id: int | None,
    *,
    status: str,
    error: str | None,
) -> None:
    if run_id is None:
        return
    try:
        async with session_factory() as session:
            run = await session.get(JobRun, run_id)
            if run is None:
                return
            run.status = status
            run.finished_at = datetime.now(UTC)
            run.error = error
            await session.commit()
    except Exception as exc:
        _logger.warning("cron_run_not_closed", run_id=run_id, error=str(exc))


def recorded(coroutine: Callable[[dict[str, Any]], Awaitable[Any]]) -> Any:
    async def run(ctx: dict[str, Any]) -> Any:
        name = coroutine.__name__
        run_id = await _open_cron_run(ctx["session_factory"], name)
        started = datetime.now(UTC)
        try:
            result = await coroutine(ctx)
        except BaseException as exc:
            elapsed = (datetime.now(UTC) - started).total_seconds()
            _logger.error(
                "cron_job_ended_early",
                job=name,
                elapsed_seconds=round(elapsed, 1),
                error_type=type(exc).__name__,
            )
            await _close_cron_run(
                ctx["session_factory"],
                run_id,
                status="cancelled" if isinstance(exc, CancelledError) else "failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        elapsed = (datetime.now(UTC) - started).total_seconds()
        _logger.info("cron_job_finished", job=name, elapsed_seconds=round(elapsed, 1))
        await _close_cron_run(ctx["session_factory"], run_id, status="success", error=None)
        return result

    run.__name__ = coroutine.__name__
    run.__qualname__ = coroutine.__qualname__
    return run


class WorkerSettings:
    functions: ClassVar = [
        func(ingest_dataset, timeout=INGEST_JOB_TIMEOUT),
        func(ingest_all, timeout=INGEST_JOB_TIMEOUT),
        run_admin_job,
        sweep_ingestion_retention,
        func(generate_sale_packet, timeout=BULK_JOB_TIMEOUT),
        func(send_daily_packet_emails, timeout=BULK_JOB_TIMEOUT),
        func(send_sheriff_change_emails, timeout=BULK_JOB_TIMEOUT),
        func(build_daily_signals, timeout=BULK_JOB_TIMEOUT),
        func(send_morning_briefs, timeout=BULK_JOB_TIMEOUT),
        func(summarise_conversations, timeout=BULK_JOB_TIMEOUT),
        func(recompute_verdicts, timeout=BULK_JOB_TIMEOUT),
        func(recompute_vacant_verdicts, timeout=BULK_JOB_TIMEOUT),
        func(recompute_distress, timeout=BULK_JOB_TIMEOUT),
        func(recompute_assemblage, timeout=BULK_JOB_TIMEOUT),
        func(recompute_vacancy_confidence, timeout=BULK_JOB_TIMEOUT),
        snapshot_stats,
        check_verdict_invariants,
        reconcile_upstream_sample,
        send_weekly_digests,
        send_daily_digests,
        send_saved_search_match_alerts,
        send_deal_reminder_emails,
        send_sales_week_emails,
        send_ops_health_digest,
        send_ops_alerts,
    ]
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = DEFAULT_JOB_TIMEOUT
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    cron_jobs: ClassVar = [
        cron(recorded(sweep_ingestion_retention), hour=2, minute=0),
        cron(recorded(ingest_all), hour=4, minute=0, timeout=INGEST_JOB_TIMEOUT),
        cron(recorded(recompute_vacancy_confidence), hour=6, minute=30, timeout=BULK_JOB_TIMEOUT),
        cron(recorded(recompute_vacant_verdicts), hour=7, minute=0, timeout=BULK_JOB_TIMEOUT),
        cron(recorded(recompute_distress), hour=8, minute=0, timeout=BULK_JOB_TIMEOUT),
        cron(recorded(recompute_assemblage), hour=8, minute=30, timeout=BULK_JOB_TIMEOUT),
        cron(recorded(recompute_buyers), hour=9, minute=0),
        cron(recorded(snapshot_stats), hour=9, minute=30),
        cron(recorded(check_verdict_invariants), hour=10, minute=30),
        cron(recorded(reconcile_upstream_sample), hour=11, minute=0),
        cron(recorded(send_ops_alerts), hour=5, minute=30),
        cron(recorded(send_ops_health_digest), hour=10, minute=0),
        cron(recorded(send_sales_week_emails), weekday="mon", hour=8, minute=0),
        cron(
            recorded(recompute_verdicts), weekday="sun", hour=5, minute=0, timeout=BULK_JOB_TIMEOUT
        ),
        cron(recorded(send_daily_digests), hour=13, minute=0),
        cron(recorded(send_weekly_digests), weekday="mon", hour=13, minute=30),
        cron(recorded(send_saved_search_match_alerts), hour=9, minute=0),
        cron(recorded(send_deal_reminder_emails), hour=13, minute=45),
        cron(
            recorded(send_daily_packet_emails),
            hour={13, 14},
            minute=0,
            timeout=BULK_JOB_TIMEOUT,
        ),
        cron(recorded(send_sheriff_change_emails), hour=5, minute=45, timeout=BULK_JOB_TIMEOUT),
        # After the ingest (04:00, ~1h) and the sheriff change pass (05:45).
        cron(recorded(build_daily_signals), hour=6, minute=15, timeout=BULK_JOB_TIMEOUT),
        # 07:00 America/New_York on both sides of DST; the job checks the local clock.
        cron(
            recorded(send_morning_briefs),
            hour={11, 12},
            minute=0,
            timeout=BULK_JOB_TIMEOUT,
        ),
        cron(recorded(summarise_conversations), hour=3, minute=30, timeout=BULK_JOB_TIMEOUT),
    ]
