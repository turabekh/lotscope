from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import Settings
from lotscope.ops.alerts import (
    detect_new_failures,
    send_ops_digest,
    send_ops_failure_alerts,
)

pytestmark = pytest.mark.integration


class _FakeSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send(
        self, *, to: str, subject: str, html: str, text: str, attachment: object = None
    ) -> None:
        self.messages.append({"to": to, "subject": subject})


class _Ctx:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _SF:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _Ctx:
        return _Ctx(self._session)


def _factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return cast("async_sessionmaker[AsyncSession]", _SF(session))


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        secret_key="test-secret-key-test-secret-key-32",
        app_base_url="https://app.test",
    )


async def _admin(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('ops@example.com', 'x', 'admin', 'pro', true)"
        )
    )


async def _add_failed_job(session: AsyncSession, uid: int, label: str) -> None:
    await session.execute(
        text(
            "INSERT INTO job_run (job_id, label, kind, status, market_code, triggered_by, error) "
            "VALUES ('ingest:phl:opa', :label, 'ingest', 'failed', 'phl', :uid, 'boom')"
        ),
        {"label": label, "uid": uid},
    )


async def test_baseline_suppresses_backlog_then_alerts_new_job(db_session: AsyncSession) -> None:
    await _admin(db_session)
    uid = await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'ops@example.com'"))
    await _add_failed_job(db_session, uid, "old failure")
    await db_session.flush()

    baseline = await detect_new_failures(db_session, advance=True)
    assert baseline.is_empty

    await _add_failed_job(db_session, uid, "new failure")
    await db_session.flush()

    second = await detect_new_failures(db_session, advance=True)
    assert [job.label for job in second.jobs] == ["new failure"]

    third = await detect_new_failures(db_session, advance=True)
    assert third.is_empty


async def test_failed_dataset_not_realerted_until_new_attempt(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO dataset_freshness "
            "(market_code, dataset, status, last_attempt_at) "
            "VALUES ('phl', 'opa_properties_public', 'failed', now() - interval '1 hour')"
        )
    )
    await db_session.flush()

    assert (await detect_new_failures(db_session, advance=True)).is_empty
    assert (await detect_new_failures(db_session, advance=True)).is_empty

    await db_session.execute(
        text(
            "UPDATE dataset_freshness SET last_attempt_at = now() "
            "WHERE market_code = 'phl' AND dataset = 'opa_properties_public'"
        )
    )
    await db_session.flush()

    fresh = await detect_new_failures(db_session, advance=True)
    assert [d.dataset for d in fresh.datasets] == ["opa_properties_public"]


async def test_failure_alert_emails_admins_and_is_quiet_when_none(
    db_session: AsyncSession,
) -> None:
    await _admin(db_session)
    uid = await db_session.scalar(text("SELECT id FROM app_user WHERE email = 'ops@example.com'"))
    await detect_new_failures(db_session, advance=True)
    await _add_failed_job(db_session, uid, "nightly ingest")
    await db_session.flush()

    sender = _FakeSender()
    sent = await send_ops_failure_alerts(_factory(db_session), sender, _settings())
    assert sent == 1
    assert sender.messages[0]["to"] == "ops@example.com"
    assert "failure" in sender.messages[0]["subject"].lower()

    quiet = _FakeSender()
    again = await send_ops_failure_alerts(_factory(db_session), quiet, _settings())
    assert again == 0
    assert quiet.messages == []


async def test_ops_digest_quiet_when_green_and_sends_on_red(db_session: AsyncSession) -> None:
    await _admin(db_session)
    await db_session.flush()

    quiet = _FakeSender()
    assert await send_ops_digest(_factory(db_session), quiet, _settings()) == 0
    assert quiet.messages == []

    await db_session.execute(
        text(
            "INSERT INTO dataset_freshness (market_code, dataset, status, last_attempt_at) "
            "VALUES ('phl', 'opa_properties_public', 'failed', now())"
        )
    )
    await db_session.flush()

    loud = _FakeSender()
    assert await send_ops_digest(_factory(db_session), loud, _settings()) == 1
    assert loud.messages[0]["to"] == "ops@example.com"
