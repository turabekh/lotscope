from asyncio import CancelledError
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.admin.service import reap_orphaned_runs
from lotscope.worker import _reap_orphans, recorded

pytestmark = pytest.mark.integration


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


async def _runs(session: AsyncSession) -> list[Any]:
    return list(
        await session.execute(
            text("SELECT label, kind, status, started_at, finished_at, error FROM job_run")
        )
    )


async def test_a_finished_cron_run_records_its_duration(db_session: AsyncSession) -> None:
    async def nightly_thing(ctx: dict[str, Any]) -> int:
        return 7

    result = await recorded(nightly_thing)({"session_factory": _Factory(db_session)})

    rows = await _runs(db_session)
    assert result == 7
    assert len(rows) == 1
    assert rows[0].kind == "cron"
    assert rows[0].status == "success"
    assert rows[0].started_at is not None
    assert rows[0].finished_at is not None


async def test_a_cancelled_cron_run_is_recorded_rather_than_vanishing(
    db_session: AsyncSession,
) -> None:
    async def killed_thing(ctx: dict[str, Any]) -> int:
        raise CancelledError

    with pytest.raises(CancelledError):
        await recorded(killed_thing)({"session_factory": _Factory(db_session)})

    rows = await _runs(db_session)
    assert len(rows) == 1
    assert rows[0].status == "cancelled"
    assert rows[0].finished_at is not None


async def test_the_wrapper_keeps_the_name_arq_schedules_it_under() -> None:
    async def ingest_all(ctx: dict[str, Any]) -> None:
        return None

    assert recorded(ingest_all).__name__ == "ingest_all"
    assert recorded(ingest_all).__qualname__ == ingest_all.__qualname__


async def test_a_run_whose_worker_died_is_closed_when_the_worker_comes_back(
    db_session: AsyncSession,
) -> None:
    """The row a killed process left behind says `running` and nothing ever contradicts it.

    This is what production showed: `cron:recompute_distress` opened at 08:00, the deploy
    recreated the worker container three minutes later, and the row still read `running`
    hours afterwards. Four `cron:recompute_vacant_verdicts` rows had been sitting that way
    since August.
    """
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at) VALUES "
            "('cron:recompute_distress', 'recompute_distress', 'cron', 'running', "
            "now() - interval '6 hours'), "
            "('recompute:verdicts', 'verdicts', 'recompute', 'running', "
            "now() - interval '40 days'), "
            "('ingest:phl:opa', 'opa', 'ingest', 'queued', null)"
        )
    )
    await db_session.flush()

    reaped = await reap_orphaned_runs(db_session)

    rows = {row.label: row for row in await _runs(db_session)}
    assert reaped == 2
    assert rows["recompute_distress"].status == "interrupted"
    assert rows["recompute_distress"].finished_at is not None
    assert "worker" in (rows["recompute_distress"].error or "")
    assert rows["verdicts"].status == "interrupted"
    # A queued job is waiting in Redis, which outlives the process. The worker that just
    # started is about to run it, so closing it here would lose a job that never ran.
    assert rows["opa"].status == "queued"
    assert rows["opa"].finished_at is None


async def test_the_worker_reaps_on_the_way_up(db_session: AsyncSession) -> None:
    """A reaper nothing calls is the same bug with more code."""
    await db_session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, started_at) VALUES "
            "('cron:ingest_all', 'ingest_all', 'cron', 'running', now() - interval '2 days')"
        )
    )
    await db_session.flush()

    await _reap_orphans(_Factory(db_session))

    rows = await _runs(db_session)
    assert rows[0].status == "interrupted"
