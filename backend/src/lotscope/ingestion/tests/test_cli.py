import pytest

from lotscope.ingestion import cli


class _BoomError(Exception):
    pass


async def test_run_targets_continues_past_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def ok(_factory: object, _settings: object) -> int:
        calls.append("ok")
        return 3

    async def boom(_factory: object, _settings: object) -> int:
        calls.append("boom")
        raise _BoomError("upstream 400")

    monkeypatch.setattr(cli, "INGEST_JOBS", {"a": ok, "boom": boom, "b": ok})

    failures = await cli.run_targets(object(), object(), ["a", "boom", "b"])  # type: ignore[arg-type]

    assert failures == ["boom"]
    assert calls == ["ok", "boom", "ok"]


async def test_run_targets_no_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ok(_factory: object, _settings: object) -> int:
        return 1

    monkeypatch.setattr(cli, "INGEST_JOBS", {"a": ok})

    assert await cli.run_targets(object(), object(), ["a"]) == []  # type: ignore[arg-type]
