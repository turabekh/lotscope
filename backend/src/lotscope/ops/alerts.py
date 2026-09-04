from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.admin.models import JobRun
from lotscope.core.market import MARKET_CODE, MARKET_NAME
from lotscope.ingestion.models import DatasetFreshness
from lotscope.notifications.email import EmailSender
from lotscope.ops.digest import (
    OpsAlertContent,
    OpsDigestContent,
    OpsMarketLine,
    ops_alert_subject,
    ops_digest_subject,
    render_ops_alert_html,
    render_ops_alert_text,
    render_ops_digest_html,
    render_ops_digest_text,
)
from lotscope.ops.models import OpsAlertState
from lotscope.ops.service import market_health

_JOBS_KEY = "jobs"
_FAILED_STATUSES = ("failed", "error")


@dataclass(frozen=True)
class FailedJob:
    id: int
    label: str
    market_code: str | None
    error: str | None


@dataclass(frozen=True)
class FailedDataset:
    market_code: str
    dataset: str
    detail: str | None
    last_attempt_at: datetime | None


@dataclass(frozen=True)
class NewFailures:
    jobs: list[FailedJob]
    datasets: list[FailedDataset]

    @property
    def is_empty(self) -> bool:
        return not self.jobs and not self.datasets


def _dataset_key(market_code: str, dataset: str) -> str:
    return f"dataset:{market_code}:{dataset}"


async def _upsert_state(
    session: AsyncSession,
    key: str,
    *,
    last_job_run_id: int | None = None,
    last_attempt_at: datetime | None = None,
) -> None:
    values: dict[str, Any] = {"key": key}
    if last_job_run_id is not None:
        values["last_job_run_id"] = last_job_run_id
    if last_attempt_at is not None:
        values["last_attempt_at"] = last_attempt_at
    statement = insert(OpsAlertState).values(**values)
    update_cols = {k: statement.excluded[k] for k in values if k != "key"}
    statement = statement.on_conflict_do_update(index_elements=["key"], set_=update_cols)
    await session.execute(statement)


async def detect_new_failures(session: AsyncSession, *, advance: bool) -> NewFailures:
    jobs_state = await session.get(OpsAlertState, _JOBS_KEY)
    baseline = jobs_state is None
    cursor = jobs_state.last_job_run_id if jobs_state and jobs_state.last_job_run_id else 0

    failed_jobs = (
        (
            await session.execute(
                select(JobRun)
                .where(JobRun.status.in_(_FAILED_STATUSES), JobRun.id > cursor)
                .order_by(JobRun.id)
            )
        )
        .scalars()
        .all()
    )
    failed_datasets = (
        (
            await session.execute(
                select(DatasetFreshness).where(DatasetFreshness.status.in_(_FAILED_STATUSES))
            )
        )
        .scalars()
        .all()
    )

    fresh_datasets: list[FailedDataset] = []
    for row in failed_datasets:
        state = await session.get(OpsAlertState, _dataset_key(row.market_code, row.dataset))
        last = state.last_attempt_at if state else None
        if row.last_attempt_at is not None and (last is None or row.last_attempt_at > last):
            fresh_datasets.append(
                FailedDataset(row.market_code, row.dataset, row.detail, row.last_attempt_at)
            )

    if baseline:
        if advance:
            highest = max((job.id for job in failed_jobs), default=0)
            await _upsert_state(session, _JOBS_KEY, last_job_run_id=highest)
            for dataset in fresh_datasets:
                if dataset.last_attempt_at is not None:
                    await _upsert_state(
                        session,
                        _dataset_key(dataset.market_code, dataset.dataset),
                        last_attempt_at=dataset.last_attempt_at,
                    )
        return NewFailures(jobs=[], datasets=[])

    jobs = [FailedJob(job.id, job.label, job.market_code, job.error) for job in failed_jobs]
    if advance:
        if jobs:
            await _upsert_state(session, _JOBS_KEY, last_job_run_id=max(job.id for job in jobs))
        for dataset in fresh_datasets:
            if dataset.last_attempt_at is not None:
                await _upsert_state(
                    session,
                    _dataset_key(dataset.market_code, dataset.dataset),
                    last_attempt_at=dataset.last_attempt_at,
                )
    return NewFailures(jobs=jobs, datasets=fresh_datasets)


async def _admin_emails(session: AsyncSession) -> list[str]:
    return list(
        (
            await session.execute(
                select(User.email)
                .where(User.role == "admin", User.is_active.is_(True))
                .order_by(User.email)
            )
        ).scalars()
    )


def _ops_url(settings: Any) -> str:
    return f"{settings.app_base_url.rstrip('/')}/admin/ops"


async def build_ops_digest(session: AsyncSession, now: datetime) -> OpsDigestContent:
    lines: list[OpsMarketLine] = []
    health = await market_health(session, MARKET_CODE, now)
    if health is not None:
        red = [(d.dataset, d.reason) for d in health.datasets if d.freshness == "red"]
        amber = [(d.dataset, d.reason) for d in health.datasets if d.freshness == "amber"]
        if red or amber:
            lines.append(
                OpsMarketLine(
                    market_code=MARKET_CODE,
                    name=MARKET_NAME,
                    health_status=health.health.status,
                    red=red,
                    amber=amber,
                    blockers=[],
                )
            )
    return OpsDigestContent(markets=lines, generated_at=now)


async def send_ops_digest(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Any,
) -> int:
    if sender is None:
        return 0
    now = datetime.now(UTC)
    async with session_factory() as session:
        content = await build_ops_digest(session, now)
        recipients = await _admin_emails(session)
    trigger = content.red_count > 0 or any(line.amber for line in content.markets)
    if not trigger or not recipients:
        return 0
    subject = ops_digest_subject(content)
    ops_url = _ops_url(settings)
    html = render_ops_digest_html(content, ops_url=ops_url)
    text = render_ops_digest_text(content, ops_url=ops_url)
    for email in recipients:
        await sender.send(to=email, subject=subject, html=html, text=text)
    return len(recipients)


async def send_ops_failure_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Any,
) -> int:
    if sender is None:
        return 0
    async with session_factory() as session:
        failures = await detect_new_failures(session, advance=True)
        recipients = await _admin_emails(session)
        await session.commit()
    if failures.is_empty or not recipients:
        return 0
    content = OpsAlertContent(
        jobs=[(job.label, job.market_code, job.error) for job in failures.jobs],
        datasets=[(d.market_code, d.dataset, d.detail) for d in failures.datasets],
    )
    subject = ops_alert_subject(content)
    ops_url = _ops_url(settings)
    html = render_ops_alert_html(content, ops_url=ops_url)
    text = render_ops_alert_text(content, ops_url=ops_url)
    for email in recipients:
        await sender.send(to=email, subject=subject, html=html, text=text)
    return len(recipients)
