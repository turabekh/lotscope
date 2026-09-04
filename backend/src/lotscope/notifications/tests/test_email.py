from email.message import EmailMessage
from typing import Any

from structlog.testing import capture_logs

from lotscope.core.config import Settings
from lotscope.notifications.email import SmtpEmailSender, get_email_sender


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "_env_file": None,
        "secret_key": "test-secret-key-test-secret-key-32",
        "smtp_host": "smtp.example.test",
    }
    base.update(overrides)
    return Settings(**base)


def _capture(sender: SmtpEmailSender) -> list[EmailMessage]:
    captured: list[EmailMessage] = []
    sender._send_sync = captured.append  # type: ignore[method-assign, assignment]
    return captured


async def test_disabled_when_smtp_host_blank() -> None:
    assert get_email_sender(_settings(smtp_host=None)) is None


async def test_list_unsubscribe_and_reply_to_headers() -> None:
    sender = SmtpEmailSender(_settings(email_reply_to="support@parcelphl.online"))
    captured = _capture(sender)

    await sender.send(
        to="user@example.com",
        subject="Digest",
        html="<b>hi</b>",
        text="hi",
        list_unsubscribe="https://parcelphl.online/unsub?token=abc",
    )

    assert len(captured) == 1
    message = captured[0]
    assert message["Reply-To"] == "support@parcelphl.online"
    assert message["List-Unsubscribe"] == "<https://parcelphl.online/unsub?token=abc>"
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["From"] == "LotScope PHL <alerts@parcelphl.online>"


async def test_no_optional_headers_by_default() -> None:
    sender = SmtpEmailSender(_settings())
    captured = _capture(sender)

    await sender.send(to="user@example.com", subject="Ops", html="<b>x</b>", text="x")

    message = captured[0]
    assert message["Reply-To"] is None
    assert message["List-Unsubscribe"] is None


async def test_allowlist_suppresses_unlisted_recipients() -> None:
    sender = SmtpEmailSender(_settings(email_allowlist=["Owner@parcelphl.online"]))
    captured = _capture(sender)

    await sender.send(to="stranger@example.com", subject="Digest", html="<b>x</b>", text="x")
    assert captured == []

    await sender.send(to="owner@PARCELPHL.online", subject="Digest", html="<b>x</b>", text="x")
    assert len(captured) == 1


async def test_a_suppressed_send_warns_with_the_domain_and_not_the_address() -> None:
    sender = SmtpEmailSender(_settings(email_allowlist=["owner@parcelphl.online"]))
    _capture(sender)

    with capture_logs() as events:
        await sender.send(to="Stranger@Example.com", subject="Confirm", html="x", text="x")

    assert events == [
        {
            "event": "email_suppressed_by_allowlist",
            "log_level": "warning",
            "subject": "Confirm",
            "recipient_domain": "example.com",
        }
    ]
