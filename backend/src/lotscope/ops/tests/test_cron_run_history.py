from asyncio import CancelledError
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.worker import recorded

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
