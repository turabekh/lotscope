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

    monkeypatch.setattr(
        cli, "INGEST_JOBS", {("phl", "a"): ok, ("phl", "boom"): boom, ("phl", "b"): ok}
    )

    failures = await cli.run_targets(
        object(),  # type: ignore[arg-type]
        object(),  # type: ignore[arg-type]
        "phl",
        ["a", "boom", "b"],
    )

    assert failures == ["boom"]
    assert calls == ["ok", "boom", "ok"]


async def test_run_targets_no_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ok(_factory: object, _settings: object) -> int:
        return 1

    monkeypatch.setattr(cli, "INGEST_JOBS", {("phl", "a"): ok})

    assert (
        await cli.run_targets(object(), object(), "phl", ["a"]) == []  # type: ignore[arg-type]
    )
