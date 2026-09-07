"""Where an unhandled exception goes.

An error that only reaches the container's stdout is an error nobody is told about.
Everything unhandled — a request that 500s, a worker job that raises, a cron that dies
— lands here, with enough context to reproduce it, and then goes to exactly one place:
Sentry when a DSN is configured, and otherwise an admin email digest built from the
`error_event` table.

Capturing must never be the thing that breaks the request. Every path here swallows its
own failures and logs them, because an exception in the exception handler replaces a
500 with a 500 nobody can read.
"""

import hashlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.ops.models import ErrorEvent

_logger = get_logger("observability")

API_SOURCE = "api"
WORKER_SOURCE = "worker"
CRON_SOURCE = "cron"

_SAMPLE_LIMIT = 2000
_sentry_ready = False


def fingerprint(source: str, kind: str, where: str) -> str:
    """Type and place, not message: the same bug with a different id is the same bug."""
    digest = hashlib.sha256(f"{source}|{kind}|{where}".encode()).hexdigest()[:16]
    return f"{source}:{kind}:{where}"[:180] + f":{digest[:8]}"


def init_error_reporting(settings: Settings, component: str) -> bool:
    """Start Sentry if a DSN is set. Returns whether errors will go there."""
    global _sentry_ready
    if not settings.sentry_dsn:
        _sentry_ready = False
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=str(settings.app_env),
            release=settings.git_sha,
            traces_sample_rate=settings.sentry_traces_sample_rate,
        )
        sentry_sdk.set_tag("component", component)
    except Exception as exc:
        _logger.error("sentry_init_failed", error=str(exc))
        _sentry_ready = False
        return False
    _sentry_ready = True
    _logger.info("sentry_initialised", component=component)
    return True


def sentry_is_active() -> bool:
    return _sentry_ready


def _to_sentry(exc: BaseException, *, source: str, where: str, context: dict[str, Any]) -> bool:
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("source", source)
            scope.set_tag("where", where)
            scope.set_context("lotscope", context)
            sentry_sdk.capture_exception(exc)
    except Exception as cause:
        _logger.error("sentry_capture_failed", error=str(cause))
        return False
    return True


async def record_error_event(
    session: AsyncSession,
    exc: BaseException,
    *,
    source: str,
    where: str,
    context: dict[str, Any],
    now: datetime | None = None,
) -> str:
    """Add one occurrence to this error's row, creating it the first time."""
    moment = now or datetime.now(UTC)
    kind = type(exc).__name__
    key = fingerprint(source, kind, where)
    statement = insert(ErrorEvent).values(
        fingerprint=key,
        source=source,
        kind=kind,
        where=where,
        sample=str(exc)[:_SAMPLE_LIMIT] or None,
        context=context,
        occurrences=1,
        first_seen_at=moment,
        last_seen_at=moment,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["fingerprint"],
            set_={
                "occurrences": ErrorEvent.occurrences + 1,
                "last_seen_at": statement.excluded.last_seen_at,
                "sample": statement.excluded.sample,
                "context": statement.excluded.context,
                # An upsert is an INSERT, so `onupdate` never fires: without this the
                # tenth occurrence of a bug still says it was last written on the first.
                "updated_at": moment,
            },
        )
    )
    await session.flush()
    return key


async def capture(
    exc: BaseException,
    *,
    source: str,
    where: str,
    context: dict[str, Any],
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession] | Callable[[], Any] | None = None,
) -> None:
    """One error, one destination, and never an exception of its own."""
    _logger.error(
        "unhandled_exception",
        source=source,
        where=where,
        error_type=type(exc).__name__,
        error=str(exc),
        **{k: v for k, v in context.items() if isinstance(v, str | int | float | bool)},
    )
    if _sentry_ready and _to_sentry(exc, source=source, where=where, context=context):
        return
    if session_factory is None:
        return
    try:
        # A fresh session on purpose: the one the request or job was using is very
        # likely inside a failed transaction, and writing the error there would lose it.
        async with session_factory() as session:
            await record_error_event(session, exc, source=source, where=where, context=context)
            await session.commit()
    except Exception as cause:
        _logger.error("error_event_not_recorded", where=where, error=str(cause))


def captured(
    session_factory_from_ctx: Callable[[dict[str, Any]], Any],
) -> Callable[..., Any]:
    """Wrap an arq job so its unhandled exceptions are reported before arq retries it."""

    def decorate(job: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def run(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            try:
                return await job(ctx, *args, **kwargs)
            except Exception as exc:
                await capture(
                    exc,
                    source=WORKER_SOURCE,
                    where=job.__name__,
                    context={
                        "job": job.__name__,
                        "args": [str(a)[:120] for a in args],
                        "job_try": ctx.get("job_try"),
                    },
                    settings=ctx["settings"],
                    session_factory=session_factory_from_ctx(ctx),
                )
                raise

        run.__name__ = job.__name__
        run.__qualname__ = job.__qualname__
        return run

    return decorate
