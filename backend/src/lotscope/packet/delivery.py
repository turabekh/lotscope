from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import create_unsubscribe_token
from lotscope.buybox.models import BuyBox
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger
from lotscope.notifications.digest import (
    PACKET_EMAIL_ROWS,
    PacketEmailContent,
    PacketLotLine,
    SaleChangeContent,
    SaleChangeLine,
    packet_email_subject,
    render_packet_email_html,
    render_packet_email_text,
    render_sale_change_html,
    render_sale_change_text,
    sale_change_subject,
)
from lotscope.notifications.email import EmailAttachment, EmailSender
from lotscope.packet.models import SaleChangeNotice, SalePacket
from lotscope.packet.service import build_packet

LOOKAHEAD_DAYS = 3
CHANGE_WINDOW_HOURS = 36

_logger = get_logger(__name__)

_UPCOMING_SALE_DATES_SQL = text(
    "SELECT DISTINCT sale_date FROM sheriff_sale "
    "WHERE sale_date >= :today AND sale_date <= :horizon ORDER BY sale_date"
)

_RECENT_EVENTS_SQL = text(
    "SELECT e.id, e.parcel_number, p.address, e.sale_date, e.old_status, e.new_status, "
    "e.old_sale_date, e.new_sale_date "
    "FROM sheriff_sale_event e LEFT JOIN parcel p USING (parcel_number) "
    "WHERE e.observed_at >= :since ORDER BY e.sale_date, e.id"
)


def _money(value: float | None) -> str:
    return f"${value:,.0f}" if value is not None else "not published"


def change_line(event: dict[str, Any]) -> str:
    old_date, new_date = event["old_sale_date"], event["new_sale_date"]
    old_status, new_status = event["old_status"], event["new_status"]
    if new_date is not None and old_date is not None and new_date != old_date:
        return f"continued to {new_date.strftime('%b %-d')}"
    if new_status and new_status != old_status:
        return f"{new_status.lower()}"
    if new_status:
        return f"{new_status.lower()}"
    return "changed"


async def _recipients(session: AsyncSession) -> list[User]:
    rows = (
        await session.execute(
            select(User)
            .join(BuyBox, BuyBox.user_id == User.id)
            .where(User.is_active.is_(True), User.email_verified_at.is_not(None))
            .order_by(User.id)
        )
    ).scalars()
    return list(rows)


def _lot_lines(model: dict[str, Any]) -> list[PacketLotLine]:
    lines: list[PacketLotLine] = []
    for lot in model.get("lots", [])[:PACKET_EMAIL_ROWS]:
        offer = (
            _money(lot.get("clearing_estimate"))
            if lot.get("clearing_sufficient")
            else _money(lot.get("max_allowable_offer"))
        )
        label = "clearing" if lot.get("clearing_sufficient") else "MAO"
        lines.append(
            PacketLotLine(
                address=lot.get("address") or lot["parcel_number"],
                grade=lot["verdict"],
                opening_bid=_money(lot.get("opening_bid")),
                offer=f"{label} {offer}",
            )
        )
    return lines


async def _send_packet_email(
    sender: EmailSender, settings: Settings, user: User, packet: SalePacket
) -> None:
    model = packet.model_json or {}
    header = model.get("header", {})
    content = PacketEmailContent(
        sale_date=packet.sale_date,
        target_use=header.get("target_use", "build"),
        vacant=int(header.get("vacant", 0)),
        passing=int(header.get("passing_buy_box", 0)),
        items=_lot_lines(model),
    )
    token = create_unsubscribe_token(settings, user_id=user.id)
    packets_url = f"{settings.app_base_url.rstrip('/')}/packets"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"

    attachment = None
    if packet.pdf_path and Path(packet.pdf_path).exists():
        attachment = EmailAttachment(
            filename=f"lotscope-sale-packet-{packet.sale_date.isoformat()}.pdf",
            content=Path(packet.pdf_path).read_bytes(),
        )

    await sender.send(
        to=user.email,
        subject=packet_email_subject(content),
        html=render_packet_email_html(
            content,
            packets_url=packets_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_packet_email_text(
            content,
            packets_url=packets_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        attachment=attachment,
        list_unsubscribe=unsubscribe_url,
    )


async def send_daily_packets(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
    *,
    today: date | None = None,
    dry_run: bool = False,
) -> int:
    sent = 0
    async with session_factory() as session:
        as_of = today or datetime.now(UTC).date()
        horizon = as_of + timedelta(days=LOOKAHEAD_DAYS)
        sale_dates = [
            row[0]
            for row in (
                await session.execute(
                    _UPCOMING_SALE_DATES_SQL, {"today": as_of, "horizon": horizon}
                )
            ).all()
        ]
        users = await _recipients(session)

        for user in users:
            for sale_date in sale_dates:
                existing = (
                    await session.execute(
                        select(SalePacket).where(
                            SalePacket.user_id == user.id, SalePacket.sale_date == sale_date
                        )
                    )
                ).scalar_one_or_none()
                if existing is not None and existing.emailed_at is not None:
                    continue
                if dry_run:
                    _logger.info(
                        "packet_email_dry_run",
                        user_id=user.id,
                        sale_date=sale_date.isoformat(),
                        already_built=existing is not None,
                    )
                    sent += 1
                    continue
                if sender is None:
                    _logger.warning("packet_email_no_transport", user_id=user.id)
                    continue
                packet = await build_packet(session, user.id, sale_date)
                await _send_packet_email(sender, settings, user, packet)
                packet.emailed_at = datetime.now(UTC)
                await session.commit()
                sent += 1
                _logger.info("packet_emailed", user_id=user.id, sale_date=sale_date.isoformat())
    return sent


async def send_sale_change_alerts(
    session_factory: async_sessionmaker[AsyncSession],
    sender: EmailSender | None,
    settings: Settings,
    *,
    since: datetime | None = None,
    dry_run: bool = False,
) -> int:
    sent = 0
    async with session_factory() as session:
        cutoff = since or datetime.now(UTC) - timedelta(hours=CHANGE_WINDOW_HOURS)
        events = [
            dict(row)
            for row in (await session.execute(_RECENT_EVENTS_SQL, {"since": cutoff})).mappings()
        ]
        if not events:
            return 0

        users = await _recipients(session)
        for user in users:
            by_sale_date: dict[date, list[dict[str, Any]]] = {}
            for event in events:
                sale_date = event["sale_date"]
                if sale_date is None:
                    continue
                packet = (
                    await session.execute(
                        select(SalePacket).where(
                            SalePacket.user_id == user.id, SalePacket.sale_date == sale_date
                        )
                    )
                ).scalar_one_or_none()
                if packet is None or not _packet_contains(packet, event["parcel_number"]):
                    continue
                already = (
                    await session.execute(
                        select(SaleChangeNotice).where(
                            SaleChangeNotice.user_id == user.id,
                            SaleChangeNotice.event_id == event["id"],
                        )
                    )
                ).scalar_one_or_none()
                if already is not None:
                    continue
                by_sale_date.setdefault(sale_date, []).append(event)

            for sale_date, grouped in sorted(by_sale_date.items()):
                content = SaleChangeContent(
                    sale_date=sale_date,
                    items=[
                        SaleChangeLine(
                            address=event.get("address") or event["parcel_number"],
                            change=change_line(event),
                        )
                        for event in grouped
                    ],
                )
                if dry_run:
                    _logger.info(
                        "sale_change_dry_run",
                        user_id=user.id,
                        sale_date=sale_date.isoformat(),
                        changes=len(grouped),
                    )
                    sent += 1
                    continue
                if sender is None:
                    _logger.warning("sale_change_no_transport", user_id=user.id)
                    continue
                await _send_change_email(sender, settings, user, content)
                for event in grouped:
                    session.add(SaleChangeNotice(user_id=user.id, event_id=event["id"]))
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()
                    continue
                sent += 1
                _logger.info(
                    "sale_change_emailed",
                    user_id=user.id,
                    sale_date=sale_date.isoformat(),
                    changes=len(grouped),
                )
    return sent


def _packet_contains(packet: SalePacket, parcel_number: str) -> bool:
    model = packet.model_json or {}
    for bucket in ("lots", "passed", "non_vacant_appendix"):
        for entry in model.get(bucket, []):
            if entry.get("parcel_number") == parcel_number:
                return True
    return False


async def _send_change_email(
    sender: EmailSender, settings: Settings, user: User, content: SaleChangeContent
) -> None:
    token = create_unsubscribe_token(settings, user_id=user.id)
    packets_url = f"{settings.app_base_url.rstrip('/')}/packets"
    unsubscribe_url = f"{settings.api_base_url.rstrip('/')}/digests/unsubscribe?token={token}"
    await sender.send(
        to=user.email,
        subject=sale_change_subject(content),
        html=render_sale_change_html(
            content,
            packets_url=packets_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        text=render_sale_change_text(
            content,
            packets_url=packets_url,
            unsubscribe_url=unsubscribe_url,
            postal_address=settings.company_postal_address,
        ),
        list_unsubscribe=unsubscribe_url,
    )
