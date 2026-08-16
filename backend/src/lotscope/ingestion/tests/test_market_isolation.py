from asyncio import CancelledError
from typing import Any

import pytest

from lotscope.ingestion import jobs
from lotscope.ingestion.errors import IngestionError


@pytest.fixture
def three_datasets(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls: dict[str, int] = {"first": 0, "second": 0, "third": 0}

    async def first(_factory: Any, _settings: Any) -> int:
        calls["first"] += 1
        raise RuntimeError("upstream is down")

    async def second(_factory: Any, _settings: Any) -> int:
        calls["second"] += 1
        return 5

    async def third(_factory: Any, _settings: Any) -> int:
        calls["third"] += 1
        return 7

    monkeypatch.setattr(
        jobs,
        "INGEST_JOBS",
        {("tst", "first"): first, ("tst", "second"): second, ("tst", "third"): third},
    )
    return calls


async def test_one_failing_dataset_does_not_stop_the_others(
    three_datasets: dict[str, int],
) -> None:
    with pytest.raises(IngestionError) as caught:
        await jobs.ingest_market(None, None, "tst")  # type: ignore[arg-type]

    assert three_datasets == {"first": 1, "second": 1, "third": 1}
    assert "first" in str(caught.value)
    assert "1 of 3" in str(caught.value)


async def test_cancellation_stops_the_market_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reached: list[str] = []

    async def cancelled(_factory: Any, _settings: Any) -> int:
        raise CancelledError

    async def later(_factory: Any, _settings: Any) -> int:
        reached.append("later")
        return 1

    monkeypatch.setattr(
        jobs, "INGEST_JOBS", {("tst", "cancelled"): cancelled, ("tst", "later"): later}
    )

    with pytest.raises(CancelledError):
        await jobs.ingest_market(None, None, "tst")  # type: ignore[arg-type]

    assert reached == []
