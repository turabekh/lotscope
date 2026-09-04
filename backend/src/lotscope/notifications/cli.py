import asyncio
from argparse import ArgumentParser, Namespace
from email.utils import make_msgid

from lotscope.core.config import get_settings
from lotscope.core.logging import configure_logging
from lotscope.notifications.email import get_email_sender

_SUBJECT = "LotScope transport test"


async def _send(address: str) -> int:
    settings = get_settings()
    configure_logging(settings)
    sender = get_email_sender(settings)
    if sender is None:
        print("No email transport is configured (SMTP_HOST is unset). Nothing was sent.")
        return 1

    transport = type(sender).__name__
    host = settings.smtp_host
    message_id = make_msgid(domain=settings.email_from.split("@")[-1])
    body = (
        "This is a LotScope transport test. If you are reading it, outbound email works.\n\n"
        f"Message-ID: {message_id}\n"
    )
    try:
        await sender.send(
            to=address,
            subject=_SUBJECT,
            html=f"<p>This is a LotScope transport test.</p><p>{message_id}</p>",
            text=body,
        )
    except Exception as error:
        print(f"transport: {transport} via {host}")
        print(f"FAILED: {error}")
        return 1

    print(f"transport:  {transport} via {host}:{settings.smtp_port}")
    print(f"from:       {settings.email_from}")
    print(f"to:         {address}")
    print(f"message-id: {message_id}  (set by us; smtplib discards the server's queue id)")
    if settings.email_allowlist:
        allowed = address.strip().lower() in {
            entry.strip().lower() for entry in settings.email_allowlist
        }
        print(f"allowlist:  {'delivered' if allowed else 'SUPPRESSED — address not allowlisted'}")
    return 0


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="lotscope email")
    sub = parser.add_subparsers(dest="command", required=True)
    test = sub.add_parser("test", help="Send one message through the configured transport.")
    test.add_argument("address")
    return parser


def main(argv: list[str] | None = None) -> None:
    args: Namespace = build_parser().parse_args(argv)
    raise SystemExit(asyncio.run(_send(args.address)))


if __name__ == "__main__":
    main()
