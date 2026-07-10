from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope import worker
from lotscope.admin.catalog import (
    CATALOG,
    CATALOG_BY_ID,
    INGEST_KIND,
    RECOMPUTE_KIND,
    ingest_job_id,
)
from lotscope.admin.models import JobRun
from lotscope.admin.service import enqueue_job, job_catalog
from lotscope.api.app import create_app
from lotscope.api.deps import get_arq_pool, get_current_user, get_session
from lotscope.core.config import Settings
from lotscope.core.errors import ConflictError, NotFoundError
from lotscope.ingestion.jobs import INGEST_JOBS
from lotscope.worker import run_admin_job


class _FakeEnqueuer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, function: str, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((function, args))
        return SimpleNamespace(job_id="arq-test-1")


class _SessionCtx:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False


def _reusing_factory(session: AsyncSession) -> Any:
    return lambda: _SessionCtx(session)


async def _admin_user(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('admin@example.com', 'x', 'admin', 'enterprise', true)"
        )
    )
    await session.flush()
    user_id = await session.scalar(
        text("SELECT id FROM app_user WHERE email = 'admin@example.com'")
    )
    return int(user_id)


def test_catalog_covers_every_ingest_job() -> None:
    ingest_ids = {ingest_job_id(market, dataset) for (market, dataset) in INGEST_JOBS}
    catalog_ingest_ids = {spec.id for spec in CATALOG if spec.kind == INGEST_KIND}
    assert ingest_ids == catalog_ingest_ids
    assert len(CATALOG_BY_ID) == len(CATALOG)


def test_worker_dispatch_stays_in_sync_with_catalog() -> None:
    recompute_ids = {spec.id for spec in CATALOG if spec.kind == RECOMPUTE_KIND}
    assert recompute_ids == set(worker._RECOMPUTE_DISPATCH)
    for spec in CATALOG:
        if spec.kind == INGEST_KIND:
            assert (spec.market, spec.dataset) in INGEST_JOBS


@pytest.mark.integration
async def test_enqueue_creates_queued_run(db_session: AsyncSession) -> None:
    user_id = await _admin_user(db_session)
    enqueuer = _FakeEnqueuer()

    summary = await enqueue_job(
        db_session, enqueuer, job_id="recompute:distress", triggered_by=user_id
    )

    assert summary.status == "queued"
    assert summary.job_id == "recompute:distress"
    assert enqueuer.calls == [("run_admin_job", (summary.id,))]
    run = await db_session.get(JobRun, summary.id)
    assert run is not None
    assert run.arq_job_id == "arq-test-1"
    assert run.triggered_by == user_id


@pytest.mark.integration
async def test_enqueue_unknown_job_is_rejected(db_session: AsyncSession) -> None:
    user_id = await _admin_user(db_session)
    with pytest.raises(NotFoundError):
        await enqueue_job(
            db_session, _FakeEnqueuer(), job_id="ingest:hbg:not_a_dataset", triggered_by=user_id
        )


@pytest.mark.integration
async def test_enqueue_rejects_duplicate_active_run(db_session: AsyncSession) -> None:
    user_id = await _admin_user(db_session)
    enqueuer = _FakeEnqueuer()
    await enqueue_job(db_session, enqueuer, job_id="recompute:distress", triggered_by=user_id)
    with pytest.raises(ConflictError):
        await enqueue_job(db_session, enqueuer, job_id="recompute:distress", triggered_by=user_id)


@pytest.mark.integration
async def test_run_admin_job_marks_success(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _dispatch(session_factory: Any, settings: Any, job_id: str) -> int:
        return 42

    monkeypatch.setattr(worker, "_dispatch_admin_job", _dispatch)
    user_id = await _admin_user(db_session)
    run = JobRun(
        job_id="recompute:distress",
        label="Recompute distress index",
        kind="recompute",
        status="queued",
        triggered_by=user_id,
    )
    db_session.add(run)
    await db_session.flush()

    result = await run_admin_job(
        {"session_factory": _reusing_factory(db_session), "settings": None}, run.id
    )

    assert result == 42
    refreshed = await db_session.get(JobRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "success"
    assert refreshed.result_count == 42
    assert refreshed.started_at is not None
    assert refreshed.finished_at is not None


@pytest.mark.integration
async def test_run_admin_job_records_failure(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(session_factory: Any, settings: Any, job_id: str) -> int:
        raise RuntimeError("upstream 500")

    monkeypatch.setattr(worker, "_dispatch_admin_job", _boom)
    user_id = await _admin_user(db_session)
    run = JobRun(
        job_id="recompute:distress",
        label="Recompute distress index",
        kind="recompute",
        status="queued",
        triggered_by=user_id,
    )
    db_session.add(run)
    await db_session.flush()

    result = await run_admin_job(
        {"session_factory": _reusing_factory(db_session), "settings": None}, run.id
    )

    assert result == 0
    refreshed = await db_session.get(JobRun, run.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error is not None
    assert "upstream 500" in refreshed.error


@pytest.mark.integration
async def test_job_catalog_reports_latest_run(db_session: AsyncSession) -> None:
    user_id = await _admin_user(db_session)
    older = JobRun(
        job_id="recompute:distress",
        label="Recompute distress index",
        kind="recompute",
        status="success",
        result_count=1,
        triggered_by=user_id,
    )
    db_session.add(older)
    await db_session.flush()
    newer = JobRun(
        job_id="recompute:distress",
        label="Recompute distress index",
        kind="recompute",
        status="failed",
        triggered_by=user_id,
    )
    db_session.add(newer)
    await db_session.flush()

    catalog = await job_catalog(db_session)
    distress = next(entry for entry in catalog if entry.id == "recompute:distress")
    assert distress.latest_run is not None
    assert distress.latest_run.id == newer.id
    assert distress.latest_run.status == "failed"
    untriggered = next(entry for entry in catalog if entry.id == "recompute:assemblage")
    assert untriggered.latest_run is None


def _admin_app(session: AsyncSession, pool: Any, *, admin_id: int) -> FastAPI:
    app = create_app()
    app.state.settings = Settings(
        _env_file=None, secret_key="test-secret-key-that-is-at-least-32-bytes-long"
    )

    async def _session() -> Any:
        yield session

    def _admin() -> Any:
        return SimpleNamespace(id=admin_id, role="admin")

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[get_current_user] = _admin
    app.dependency_overrides[get_arq_pool] = lambda: pool
    return app


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.integration
async def test_run_job_endpoint_requires_admin(db_session: AsyncSession) -> None:
    app = _admin_app(db_session, _FakeEnqueuer(), admin_id=1)

    def _member() -> Any:
        return SimpleNamespace(id=1, role="user")

    app.dependency_overrides[get_current_user] = _member
    async with _client(app) as client:
        resp = await client.post("/admin/jobs/run", json={"job_id": "recompute:distress"})
    assert resp.status_code == 403


@pytest.mark.integration
async def test_admin_can_enqueue_and_list_runs(db_session: AsyncSession) -> None:
    admin_id = await _admin_user(db_session)
    pool = _FakeEnqueuer()
    app = _admin_app(db_session, pool, admin_id=admin_id)

    async with _client(app) as client:
        run = await client.post("/admin/jobs/run", json={"job_id": "recompute:distress"})
        runs = await client.get("/admin/jobs/runs")

    assert run.status_code == 200
    body = run.json()
    assert body["job_id"] == "recompute:distress"
    assert body["status"] == "queued"
    assert pool.calls == [("run_admin_job", (body["id"],))]
    assert runs.status_code == 200
    assert [r["id"] for r in runs.json()] == [body["id"]]
