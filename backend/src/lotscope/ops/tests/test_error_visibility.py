"""Errors reach somebody, once per bug rather than once per throw; stopped crons are seen."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.config import Settings
from lotscope.core.observability import API_SOURCE, capture, record_error_event
from lotscope.ops.cron_schedule import CRON_SCHEDULE, CronSpec, missed_since, previous_fires
from lotscope.ops.errors import build_error_digest, send_error_digest
from lotscope.ops.models import ErrorEvent
from lotscope.ops.service import stale_cron_jobs

pytestmark = pytest.mark.integration


class _Outbox:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


class _Factory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> Any:
        session = self._session

        class _Ctx:
            async def __aenter__(self) -> AsyncSession:
                return session

            async def __aexit__(self, *args: object) -> None:
                return None

        return _Ctx()


def _factory(session: AsyncSession) -> Any:
    """The test's own session, dressed as a session factory."""
    return cast("Any", _Factory(session))


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {"error_digest_minutes": 15, "app_base_url": "https://app.test"}
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def _admin(session: AsyncSession, email: str = "ops@example.com") -> None:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'admin', 'pro', true)"
        ),
        {"e": email},
    )
    await session.flush()


async def test_the_same_bug_thrown_a_thousand_times_is_one_row(
    db_session: AsyncSession,
) -> None:
    for index in range(1000):
        await record_error_event(
            db_session,
            ValueError(f"row {index} is not a number"),
            source=API_SOURCE,
            where="GET /parcels/{parcel_number}",
            context={"path": f"/parcels/phl:{index}"},
        )

    rows = (await db_session.execute(select_error_events())).scalars().all()
    assert len(rows) == 1
    assert rows[0].occurrences == 1000
    assert rows[0].kind == "ValueError"
    # The last message is kept, so the digest can show a real error rather than a class.
    assert rows[0].sample == "row 999 is not a number"


def select_error_events() -> Any:
    from sqlalchemy import select

    return select(ErrorEvent).order_by(ErrorEvent.fingerprint)


async def test_the_same_exception_at_two_places_stays_two_rows(
    db_session: AsyncSession,
) -> None:
    await record_error_event(
        db_session, KeyError("a"), source="worker", where="ingest_all", context={}
    )
    await record_error_event(
        db_session, KeyError("a"), source="worker", where="rebuild_screen_index", context={}
    )

    rows = (await db_session.execute(select_error_events())).scalars().all()
    assert len(rows) == 2


async def test_the_digest_reports_an_error_once_and_stays_quiet_until_it_throws_again(
    db_session: AsyncSession,
) -> None:
    await _admin(db_session)
    await record_error_event(
        db_session, RuntimeError("boom"), source="worker", where="ingest_all", context={}
    )
    outbox = _Outbox()
    settings = _settings()

    first = await send_error_digest(_factory(db_session), outbox, settings)
    quiet = await send_error_digest(_factory(db_session), outbox, settings)

    # It throws again: the same bug, but new information, so it is reported again.
    await record_error_event(
        db_session, RuntimeError("boom"), source="worker", where="ingest_all", context={}
    )
    again = await send_error_digest(_factory(db_session), outbox, settings)

    assert first == 1
    assert quiet == 0
    assert again == 1
    assert len(outbox.sent) == 2
    assert "RuntimeError" in outbox.sent[0]["text"]
    assert "ingest_all" in outbox.sent[0]["text"]


async def test_the_digest_counts_only_what_is_new_since_the_last_one(
    db_session: AsyncSession,
) -> None:
    for _ in range(5):
        await record_error_event(
            db_session, TimeoutError("slow"), source="api", where="GET /search", context={}
        )
    await build_error_digest(db_session, window_minutes=15)
    for _ in range(3):
        await record_error_event(
            db_session, TimeoutError("slow"), source="api", where="GET /search", context={}
        )

    digest = await build_error_digest(db_session, window_minutes=15)

    assert len(digest.lines) == 1
    assert digest.lines[0].new_occurrences == 3
    assert digest.lines[0].total_occurrences == 8


async def test_nothing_is_marked_reported_when_there_is_nowhere_to_report_it(
    db_session: AsyncSession,
) -> None:
    """Otherwise the first errors of a deployment vanish into an unconfigured mailbox."""
    await record_error_event(
        db_session, RuntimeError("early"), source="api", where="GET /health", context={}
    )

    assert await send_error_digest(_factory(db_session), None, _settings()) == 0

    await _admin(db_session, "late-admin@example.com")
    outbox = _Outbox()
    assert await send_error_digest(_factory(db_session), outbox, _settings()) == 1


async def test_an_unhandled_route_error_is_captured_with_the_route_not_the_path(
    db_session: AsyncSession,
) -> None:
    from lotscope.api.errors import register_exception_handlers

    app = FastAPI()
    app.state.session_factory = _factory(db_session)
    register_exception_handlers(app)

    @app.get("/boom/{parcel_number}")
    async def boom(parcel_number: str) -> None:
        raise ZeroDivisionError(f"nothing divides {parcel_number}")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/boom/phl:1")
        await client.get("/boom/phl:2")

    assert first.status_code == 500
    rows = (await db_session.execute(select_error_events())).scalars().all()
    # Two parcels, one bug: the route pattern is the fingerprint, not the filled-in path.
    assert len(rows) == 1
    assert rows[0].occurrences == 2
    assert rows[0].where == "GET /boom/{parcel_number}"
    assert rows[0].context is not None
    assert rows[0].context["path"] == "/boom/phl:2"


async def test_capturing_never_raises_even_with_no_database(db_session: AsyncSession) -> None:
    class _Broken:
        def __call__(self) -> Any:
            raise RuntimeError("the pool is gone")

    await capture(
        ValueError("x"),
        source="api",
        where="GET /whatever",
        context={},
        settings=_settings(),
        session_factory=_Broken(),
    )


def test_the_worker_schedules_exactly_the_shared_timetable() -> None:
    """A stale-job check against a timetable the worker does not run reports on nothing."""
    from lotscope.worker import WorkerSettings

    scheduled = {job.name for job in WorkerSettings.cron_jobs}
    # arq names a cron `cron:<function>`, which is the same key `_open_cron_run` writes
    # into job_run.job_id and the same one readiness looks up. All three or none.
    assert scheduled == {f"cron:{spec.name}" for spec in CRON_SCHEDULE}


def test_two_scheduled_runs_back_is_two_days_for_a_daily_job() -> None:
    spec = CronSpec("recompute_distress", (8,))
    now = datetime(2026, 9, 6, 11, 30, tzinfo=UTC)

    fires = previous_fires(spec, now)

    assert fires == [
        datetime(2026, 9, 6, 8, 0, tzinfo=UTC),
        datetime(2026, 9, 5, 8, 0, tzinfo=UTC),
    ]
    assert missed_since(spec, now) == datetime(2026, 9, 5, 8, 0, tzinfo=UTC)


def test_a_weekly_job_looks_back_two_weeks_and_a_quarter_hourly_one_half_an_hour() -> None:
    now = datetime(2026, 9, 6, 11, 32, tzinfo=UTC)  # a Sunday

    weekly = missed_since(CronSpec("send_weekly_digests", (13,), (30,), "mon"), now)
    frequent = missed_since(CronSpec("send_error_digest_email", None, (0, 15, 30, 45)), now)

    assert weekly == datetime(2026, 8, 24, 13, 30, tzinfo=UTC)
    assert frequent == datetime(2026, 9, 6, 11, 15, tzinfo=UTC)


async def test_a_cron_that_missed_two_nights_is_reported_stale(db_session: AsyncSession) -> None:
    now = datetime.now(UTC).replace(hour=11, minute=30, second=0, microsecond=0)
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at) VALUES "
            "('cron:recompute_distress', 'recompute_distress', 'cron', 'success', :old, :old), "
            "('cron:ingest_all', 'ingest_all', 'cron', 'success', :new, :new)"
        ),
        {"old": now - timedelta(days=4), "new": now - timedelta(hours=7)},
    )
    await db_session.flush()

    stale = {job.name: job.reason for job in await stale_cron_jobs(db_session, now)}

    assert "recompute_distress" in stale
    assert "last succeeded" in stale["recompute_distress"]
    assert "ingest_all" not in stale


async def test_one_missed_night_is_not_an_alarm(db_session: AsyncSession) -> None:
    """A deploy over a job's window costs it one run. Two in a row is a stopped job."""
    now = datetime.now(UTC).replace(hour=11, minute=30, second=0, microsecond=0)
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at) VALUES "
            "('cron:recompute_distress', 'recompute_distress', 'cron', 'success', :t, :t)"
        ),
        {"t": now - timedelta(days=1, hours=3)},
    )
    await db_session.flush()

    stale = {job.name for job in await stale_cron_jobs(db_session, now)}

    assert "recompute_distress" not in stale


async def test_nothing_is_stale_before_we_were_recording(db_session: AsyncSession) -> None:
    """A fresh deployment must not report every job on the timetable as broken."""
    now = datetime.now(UTC).replace(hour=11, minute=30, second=0, microsecond=0)
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at) VALUES "
            "('cron:snapshot_stats', 'snapshot_stats', 'cron', 'success', :t, :t)"
        ),
        {"t": now - timedelta(minutes=5)},
    )
    await db_session.flush()

    assert await stale_cron_jobs(db_session, now) == []


async def test_readiness_says_which_job_stopped(db_session: AsyncSession) -> None:
    from lotscope.api.deps import get_redis, get_session
    from lotscope.api.health import router as health_router

    now = datetime.now(UTC)
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at) VALUES "
            "('cron:recompute_distress', 'recompute_distress', 'cron', 'success', :old, :old), "
            "('cron:ingest_all', 'ingest_all', 'cron', 'success', :new, :new)"
        ),
        {"old": now - timedelta(days=5), "new": now - timedelta(minutes=1)},
    )
    await db_session.flush()

    class _Redis:
        async def ping(self) -> bool:
            return True

    app = FastAPI()
    app.include_router(health_router)
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: _Redis()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        body = (await client.get("/health/ready")).json()

    assert any("recompute_distress" in line for line in body["stale_jobs"])
    assert body["status"] == "degraded"
