import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Protocol

from lotscope.core.config import Settings
from lotscope.core.logging import get_logger


def _recipient_domain(address: str) -> str:
    _, _, domain = address.strip().lower().rpartition("@")
    return domain or "unknown"


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    content: bytes
    mime_subtype: str = "pdf"


class EmailSender(Protocol):
    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        attachment: EmailAttachment | None = None,
        list_unsubscribe: str | None = None,
    ) -> None: ...


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        if not settings.smtp_host:
            raise ValueError("SMTP is not configured.")
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_password
        self._use_tls = settings.smtp_use_tls
        self._from = formataddr((settings.email_from_name, settings.email_from))
        self._reply_to = settings.email_reply_to
        self._allowlist = frozenset(address.strip().lower() for address in settings.email_allowlist)
        self._logger = get_logger("email")

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
        attachment: EmailAttachment | None = None,
        list_unsubscribe: str | None = None,
    ) -> None:
        if self._allowlist and to.strip().lower() not in self._allowlist:
            self._logger.warning(
                "email_suppressed_by_allowlist",
                subject=subject,
                recipient_domain=_recipient_domain(to),
            )
            return
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._from
        message["To"] = to
        if self._reply_to:
            message["Reply-To"] = self._reply_to
        if list_unsubscribe is not None:
            message["List-Unsubscribe"] = f"<{list_unsubscribe}>"
            message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        message.set_content(text)
        message.add_alternative(html, subtype="html")
        if attachment is not None:
            message.add_attachment(
                attachment.content,
                maintype="application",
                subtype=attachment.mime_subtype,
                filename=attachment.filename,
            )
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=30) as client:
            if self._use_tls:
                client.starttls()
            if self._user and self._password:
                client.login(self._user, self._password)
            client.send_message(message)


def get_email_sender(settings: Settings) -> EmailSender | None:
    if not settings.smtp_host:
        return None
    return SmtpEmailSender(settings)
