from lotscope.core.config import Settings
from lotscope.notifications.email import EmailSender

_SUBJECT = "Confirm your email for LotScope"


def verification_url(settings: Settings, token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/verify?token={token}"


def _text(link: str) -> str:
    return (
        "Confirm your email address to finish setting up your LotScope account:\n\n"
        f"{link}\n\n"
        "The link works once and expires in 24 hours. If you did not create an account, "
        "ignore this message and nothing will happen."
    )


def _html(link: str) -> str:
    return (
        "<p>Confirm your email address to finish setting up your LotScope account.</p>"
        f'<p><a href="{link}">Confirm my email</a></p>'
        "<p>The link works once and expires in 24 hours. If you did not create an account, "
        "ignore this message and nothing will happen.</p>"
    )


async def send_verification_email(
    sender: EmailSender, settings: Settings, *, to: str, token: str
) -> None:
    link = verification_url(settings, token)
    await sender.send(to=to, subject=_SUBJECT, html=_html(link), text=_text(link))
