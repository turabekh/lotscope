from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.buybox.schemas import BuyBoxWrite
from lotscope.buybox.service import write_buy_box
from lotscope.core.config import Settings
from lotscope.notifications.email import EmailAttachment
from lotscope.packet.delivery import (
    change_line,
    send_daily_packets,
    send_sale_change_alerts,
)
from lotscope.packet.models import SaleChangeNotice

pytestmark = pytest.mark.integration

SALE_DATE = date.today() + timedelta(days=2)
PARCEL = "phl:delivery1"


class _Sender:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

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
        self.sent.append(
            {
                "to": to,
                "subject": subject,
                "text": text,
                "html": html,
                "attachment": attachment.filename if attachment else None,
            }
        )


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        secret_key="test-secret-key-that-is-at-least-32-bytes",
        smtp_host="smtp.example.test",
    )


class _SharedSessionFactory:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> "_SharedSessionFactory":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        return None


def _factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return cast("async_sessionmaker[AsyncSession]", _SharedSessionFactory(session))


async def _user(session: AsyncSession, email: str, *, verified: bool = True) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active, "
            "email_verified_at) VALUES (:e, 'x', 'user', 'pro', true, :v)"
        ),
        {"e": email, "v": datetime.now(UTC) if verified else None},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _listing(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_standard (code, code_version, market_code, min_lot_area_sqft, "
            "min_lot_width_ft, max_height_ft, max_occupancy_pct, permitted_uses, max_units) "
            "VALUES ('RSA-5', 'delivery-1', 'phl', 640, 16, 38, 75, "
            "'[\"single_family\"]'::jsonb, 3) ON CONFLICT DO NOTHING"
        )
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, address, base_zoning_code, "
            "market_value, lot_area_sqft, frontage_ft, is_vacant, geom_local) "
            "VALUES (:p, 'phl', '1329 GROVE ST', 'RSA-5', 90000, 4000, 40, true, "
            "ST_SetSRID(ST_MakePoint(2690000, 240000), 2272))"
        ),
        {"p": PARCEL},
    )
    await session.execute(
        text(
            "INSERT INTO sheriff_sale (parcel_number, case_number, sale_type, sale_date, "
            "status, opening_bid) VALUES (:p, '2699-100', 'Tax', :d, 'Scheduled - Tax', 1600)"
        ),
        {"p": PARCEL, "d": SALE_DATE},
    )
    await session.flush()


async def _ready_user(session: AsyncSession, email: str) -> int:
    user_id = await _user(session, email)
    await write_buy_box(session, user_id, BuyBoxWrite(min_lot_sqft=None, zoning_codes=[]))
    await session.flush()
    return user_id


async def test_one_packet_email_per_user_per_sale_date_and_none_on_a_rerun(
    db_session: AsyncSession,
) -> None:
    await _listing(db_session)
    await _ready_user(db_session, "deliver-a@example.com")
    await _ready_user(db_session, "deliver-b@example.com")
    sender = _Sender()

    first = await send_daily_packets(_factory(db_session), sender, _settings(), today=date.today())
    second = await send_daily_packets(_factory(db_session), sender, _settings(), today=date.today())

    assert first == 2
    assert second == 0
    assert len(sender.sent) == 2
    assert {entry["to"] for entry in sender.sent} == {
        "deliver-a@example.com",
        "deliver-b@example.com",
    }


async def test_the_packet_email_attaches_the_pdf_and_lists_the_top_lots(
    db_session: AsyncSession,
) -> None:
    await _listing(db_session)
    await _ready_user(db_session, "deliver-c@example.com")
    sender = _Sender()

    await send_daily_packets(_factory(db_session), sender, _settings(), today=date.today())

    entry = sender.sent[0]
    assert entry["attachment"] == f"lotscope-sale-packet-{SALE_DATE.isoformat()}.pdf"
    assert SALE_DATE.isoformat() in str(entry["subject"])
    assert "nominal on tax sales" in str(entry["text"])
    assert "Unsubscribe" in str(entry["text"])


async def test_a_user_without_a_buy_box_or_a_verified_email_is_not_sent_a_packet(
    db_session: AsyncSession,
) -> None:
    await _listing(db_session)
    await _user(db_session, "no-box@example.com")
    unverified = await _user(db_session, "unverified@example.com", verified=False)
    await write_buy_box(db_session, unverified, BuyBoxWrite())
    await db_session.flush()
    sender = _Sender()

    count = await send_daily_packets(_factory(db_session), sender, _settings(), today=date.today())

    assert count == 0
    assert sender.sent == []


async def _event(session: AsyncSession, **overrides: object) -> int:
    payload: dict[str, object] = {
        "p": PARCEL,
        "case": "2699-100",
        "d": SALE_DATE,
        "old_status": "Scheduled - Tax",
        "new_status": "Postponed",
        "old_sale_date": SALE_DATE,
        "new_sale_date": SALE_DATE + timedelta(days=22),
    }
    payload.update(overrides)
    await session.execute(
        text(
            "INSERT INTO sheriff_sale_event (parcel_number, case_number, sale_date, old_status, "
            "new_status, old_sale_date, new_sale_date, observed_at) "
            "VALUES (:p, :case, :d, :old_status, :new_status, :old_sale_date, :new_sale_date, "
            "now())"
        ),
        payload,
    )
    await session.flush()
    return int(await session.scalar(text("SELECT max(id) FROM sheriff_sale_event")))


async def test_one_change_email_per_user_per_sale_date_and_none_on_a_rerun(
    db_session: AsyncSession,
) -> None:
    await _listing(db_session)
    await _ready_user(db_session, "change-a@example.com")
    await _ready_user(db_session, "change-b@example.com")
    await send_daily_packets(_factory(db_session), _Sender(), _settings(), today=date.today())
    await _event(db_session)
    await _event(db_session, new_status="Stayed", new_sale_date=SALE_DATE)
    sender = _Sender()

    first = await send_sale_change_alerts(_factory(db_session), sender, _settings())
    second = await send_sale_change_alerts(_factory(db_session), sender, _settings())

    assert first == 2
    assert second == 0
    assert len(sender.sent) == 2
    body = str(sender.sent[0]["text"])
    assert "1329 GROVE ST" in body
    assert "continued to" in body or "stayed" in body

    notices = await db_session.scalar(text("SELECT count(*) FROM sale_change_notice"))
    assert notices == 4


async def test_a_user_whose_packet_does_not_hold_the_parcel_is_not_told(
    db_session: AsyncSession,
) -> None:
    await _listing(db_session)
    await _ready_user(db_session, "unrelated@example.com")
    await _event(db_session, p="phl:not-in-any-packet")
    sender = _Sender()

    count = await send_sale_change_alerts(_factory(db_session), sender, _settings())

    assert count == 0
    assert sender.sent == []


async def test_a_change_notice_is_keyed_on_the_event_id(db_session: AsyncSession) -> None:
    await _listing(db_session)
    user_id = await _ready_user(db_session, "keyed@example.com")
    await send_daily_packets(_factory(db_session), _Sender(), _settings(), today=date.today())
    event_id = await _event(db_session)
    await send_sale_change_alerts(_factory(db_session), _Sender(), _settings())

    stored = (
        await db_session.execute(
            text("SELECT user_id, event_id FROM sale_change_notice WHERE event_id = :e"),
            {"e": event_id},
        )
    ).one()

    assert stored.user_id == user_id
    assert stored.event_id == event_id
    assert SaleChangeNotice.__tablename__ == "sale_change_notice"


def test_the_change_line_reads_as_a_person_would_say_it() -> None:
    moved = change_line(
        {
            "old_sale_date": date(2026, 9, 16),
            "new_sale_date": date(2026, 10, 8),
            "old_status": "Scheduled - Tax",
            "new_status": "Postponed",
        }
    )
    stayed = change_line(
        {
            "old_sale_date": date(2026, 9, 16),
            "new_sale_date": date(2026, 9, 16),
            "old_status": "Scheduled - Tax",
            "new_status": "Stayed",
        }
    )

    assert moved == "continued to Oct 8"
    assert stayed == "stayed"
