from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import BuyerInvite, Purchase, User

Sku = Literal["packet", "diligence"]

PACKET_SKU: Sku = "packet"
DILIGENCE_SKU: Sku = "diligence"

SKU_PRICES_CENTS: dict[str, int] = {PACKET_SKU: 4900, DILIGENCE_SKU: 19900}
SKU_LABELS: dict[str, str] = {PACKET_SKU: "Sale Packet", DILIGENCE_SKU: "Lot Diligence"}
INVITE_COMP_DAYS = 60


def price_cents(sku: str) -> int:
    if sku not in SKU_PRICES_CENTS:
        raise KeyError(f"Unknown sku {sku!r}.")
    return SKU_PRICES_CENTS[sku]


def is_comped(user: User, *, now: datetime | None = None) -> bool:
    if user.comp_until is None:
        return False
    return user.comp_until > (now or datetime.now(UTC))


async def has_paid(session: AsyncSession, user_id: int, sku: str, object_ref: str) -> bool:
    found = (
        await session.execute(
            select(Purchase).where(
                Purchase.user_id == user_id,
                Purchase.sku == sku,
                Purchase.object_ref == object_ref,
                Purchase.paid_at.is_not(None),
            )
        )
    ).scalar_one_or_none()
    return found is not None


async def may_download(
    session: AsyncSession, user: User, sku: str, object_ref: str, *, now: datetime | None = None
) -> bool:
    if is_comped(user, now=now):
        return True
    return await has_paid(session, user.id, sku, object_ref)


async def record_session(
    session: AsyncSession,
    *,
    user_id: int,
    sku: str,
    object_ref: str,
    stripe_session_id: str,
) -> Purchase:
    existing = (
        await session.execute(
            select(Purchase).where(Purchase.stripe_session_id == stripe_session_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    purchase = Purchase(
        user_id=user_id,
        sku=sku,
        object_ref=object_ref,
        stripe_session_id=stripe_session_id,
        amount_cents=price_cents(sku),
    )
    session.add(purchase)
    await session.flush()
    return purchase


async def mark_paid(
    session: AsyncSession, stripe_session_id: str, *, now: datetime | None = None
) -> Purchase | None:
    purchase = (
        await session.execute(
            select(Purchase).where(Purchase.stripe_session_id == stripe_session_id)
        )
    ).scalar_one_or_none()
    if purchase is None:
        return None
    if purchase.paid_at is None:
        purchase.paid_at = now or datetime.now(UTC)
        await session.flush()
    return purchase


async def redeem_invite(
    session: AsyncSession, user: User, *, token_key: str | None, code: str | None
) -> bool:
    invite = None
    if token_key:
        invite = await session.get(BuyerInvite, token_key)
    elif code:
        invite = (
            await session.execute(
                select(BuyerInvite).where(BuyerInvite.code == code.strip().upper())
            )
        ).scalar_one_or_none()
    if invite is None:
        return False
    now = datetime.now(UTC)
    user.comp_until = now + timedelta(days=INVITE_COMP_DAYS)
    invite.redeemed_by_user_id = user.id
    invite.redeemed_at = now
    await session.flush()
    return True
