"""The digest that tells the admins what broke, once per error rather than once per throw."""

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.logging import get_logger
from lotscope.notifications.email import EmailSender
from lotscope.ops.models import ErrorEvent

_logger = get_logger(__name__)


@dataclass(frozen=True)
class ErrorLine:
    fingerprint: str
    source: str
    kind: str
    where: str
    sample: str | None
    new_occurrences: int
    total_occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class ErrorDigest:
    lines: list[ErrorLine]
    window_minutes: int
    generated_at: datetime

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def total(self) -> int:
        return sum(line.new_occurrences for line in self.lines)


async def pending_errors(session: AsyncSession) -> list[ErrorEvent]:
    """Rows that have thrown since the last digest went out.

    `notified_at` is the whole dedup. An error that has not thrown again since it was
    reported is not reported again, however many times it threw before that.
    """
    return list(
        (
            await session.execute(
                select(ErrorEvent)
                .where(
                    (ErrorEvent.notified_at.is_(None))
                    | (ErrorEvent.last_seen_at > ErrorEvent.notified_at)
                )
                .order_by(ErrorEvent.last_seen_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def build_error_digest(
    session: AsyncSession, *, window_minutes: int, now: datetime | None = None, mark: bool = True
) -> ErrorDigest:
    moment = now or datetime.now(UTC)
    rows = await pending_errors(session)
    lines: list[ErrorLine] = []
    for row in rows:
        # Everything since the last report; the first report counts the whole history.
        already = row.notified_count if row.notified_at is not None else 0
        lines.append(
            ErrorLine(
                fingerprint=row.fingerprint,
                source=row.source,
                kind=row.kind,
                where=row.where,
                sample=row.sample,
                new_occurrences=max(row.occurrences - already, 1),
                total_occurrences=row.occurrences,
                first_seen_at=row.first_seen_at,
                last_seen_at=row.last_seen_at,
            )
        )
        if mark:
            row.notified_at = moment
            row.notified_count = row.occurrences
    if mark and rows:
        await session.flush()
    return ErrorDigest(lines=lines, window_minutes=window_minutes, generated_at=moment)


def digest_subject(digest: ErrorDigest) -> str:
    kinds = len(digest.lines)
    return f"LotScope errors: {digest.total} in {kinds} kind(s)"


def _line_text(line: ErrorLine) -> str:
    seen = line.last_seen_at.strftime("%Y-%m-%d %H:%M")
    return (
        f"[{line.source}] {line.kind} in {line.where} - {line.new_occurrences} new "
        f"({line.total_occurrences} total), last {seen} UTC\n    {line.sample or ''}"
    )


def render_digest_text(digest: ErrorDigest, *, ops_url: str) -> str:
    header = (
        f"{digest.total} unhandled error(s) since the last digest, "
        f"grouped into {len(digest.lines)} kind(s)."
    )
    return "\n".join([header, "", *[_line_text(line) for line in digest.lines], "", ops_url])


def render_digest_html(digest: ErrorDigest, *, ops_url: str) -> str:
    rows = "".join(
        "<li><strong>{kind}</strong> in <code>{where}</code> "
        "<em>({source})</em><br>{count} new, {total} total, last {seen} UTC"
        "<br><code>{sample}</code></li>".format(
            kind=escape(line.kind),
            where=escape(line.where),
            source=escape(line.source),
            count=line.new_occurrences,
            total=line.total_occurrences,
            seen=line.last_seen_at.strftime("%Y-%m-%d %H:%M"),
            sample=escape((line.sample or "")[:400]),
        )
        for line in digest.lines
    )
    return (
        f"<p>{digest.total} unhandled error(s) since the last digest, grouped into "
        f"{len(digest.lines)} kind(s).</p><ul>{rows}</ul>"
        f'<p><a href="{escape(ops_url)}">Open ops</a></p>'
    )


async def send_error_digest(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Any,
    *,
    now: datetime | None = None,
) -> int:
    from lotscope.budget.notify import admin_emails

    async with session_factory() as session:
        recipients = await admin_emails(session)
        # Nothing is marked as reported unless there is somewhere to report it to,
        # or the first errors of the deployment vanish into an unconfigured mailbox.
        digest = await build_error_digest(
            session,
            window_minutes=settings.error_digest_minutes,
            now=now,
            mark=bool(sender and recipients),
        )
        await session.commit()
    if digest.is_empty or sender is None or not recipients:
        if not digest.is_empty:
            _logger.warning("error_digest_not_sent", kinds=len(digest.lines), total=digest.total)
        return 0
    ops_url = f"{settings.app_base_url.rstrip('/')}/admin/ops"
    subject = digest_subject(digest)
    for email in recipients:
        await sender.send(
            to=email,
            subject=subject,
            html=render_digest_html(digest, ops_url=ops_url),
            text=render_digest_text(digest, ops_url=ops_url),
        )
    return len(recipients)
