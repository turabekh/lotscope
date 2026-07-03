from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import QuotaExceededError, ValidationError
from lotscope.skiptrace.models import (
    APPEAL_PACKET_REASONS,
    REASON_APPEAL_PACKET_BURN,
    REASON_SKIPTRACE_BURN,
    SKIPTRACE_REASONS,
    CreditLedgerEntry,
    SkipTraceResult,
)
from lotscope.skiptrace.provider import SkipTraceProvider
from lotscope.skiptrace.schemas import (
    CreditBalance,
    CreditLedgerItem,
    SkipTraceContactsOut,
    SkipTraceResultOut,
)

CACHE_TTL_DAYS = 90

_OWNER_SQL = text(
    "SELECT owner, owner_key, mailing_address FROM parcel WHERE parcel_number = :parcel_number"
)
_BALANCE_SQL = text(
    "SELECT coalesce(sum(delta), 0) FROM credit_ledger "
    "WHERE user_id = :user_id AND reason = ANY(:reasons)"
)
_HAS_TRACED_SQL = text(
    "SELECT EXISTS (SELECT 1 FROM credit_ledger "
    "WHERE user_id = :user_id AND reason = :reason AND ref = :owner_key)"
)


async def credit_balance(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(_BALANCE_SQL, {"user_id": user_id, "reasons": list(SKIPTRACE_REASONS)})
        or 0
    )


async def appeal_packet_balance(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            _BALANCE_SQL, {"user_id": user_id, "reasons": list(APPEAL_PACKET_REASONS)}
        )
        or 0
    )


async def spend_appeal_packet_credit(session: AsyncSession, user_id: int, ref: str) -> bool:
    statement = (
        insert(CreditLedgerEntry)
        .values(user_id=user_id, delta=-1, reason=REASON_APPEAL_PACKET_BURN, ref=ref)
        .on_conflict_do_nothing(
            index_elements=["user_id", "reason", "ref"],
            index_where=text("reason <> 'skiptrace_burn' AND ref IS NOT NULL"),
        )
        .returning(CreditLedgerEntry.id)
    )
    inserted = (await session.execute(statement)).scalar_one_or_none()
    return inserted is not None


async def get_credit_balance(
    session: AsyncSession, user_id: int, *, limit: int = 20
) -> CreditBalance:
    balance = await credit_balance(session, user_id)
    rows = (
        await session.execute(
            select(CreditLedgerEntry)
            .where(CreditLedgerEntry.user_id == user_id)
            .order_by(CreditLedgerEntry.created_at.desc())
            .limit(limit)
        )
    ).scalars()
    entries = [
        CreditLedgerItem(delta=e.delta, reason=e.reason, ref=e.ref, created_at=e.created_at)
        for e in rows
    ]
    return CreditBalance(balance=balance, entries=entries)


async def grant_credits(
    session: AsyncSession, user_id: int, amount: int, reason: str, ref: str | None
) -> bool:
    statement = (
        insert(CreditLedgerEntry)
        .values(user_id=user_id, delta=amount, reason=reason, ref=ref)
        .on_conflict_do_nothing(
            index_elements=["user_id", "reason", "ref"],
            index_where=text("reason <> 'skiptrace_burn' AND ref IS NOT NULL"),
        )
        .returning(CreditLedgerEntry.id)
    )
    inserted = (await session.execute(statement)).scalar_one_or_none()
    return inserted is not None


async def _has_traced(session: AsyncSession, user_id: int, owner_key: str) -> bool:
    return bool(
        await session.scalar(
            _HAS_TRACED_SQL,
            {"user_id": user_id, "reason": REASON_SKIPTRACE_BURN, "owner_key": owner_key},
        )
    )


async def _cached_payload(session: AsyncSession, owner_key: str) -> dict[str, Any] | None:
    cutoff = datetime.now(UTC) - timedelta(days=CACHE_TTL_DAYS)
    result = await session.get(SkipTraceResult, owner_key)
    if result is None or result.traced_at < cutoff:
        return None
    return result.payload


async def _burn(session: AsyncSession, user_id: int, owner_key: str) -> None:
    session.add(
        CreditLedgerEntry(user_id=user_id, delta=-1, reason=REASON_SKIPTRACE_BURN, ref=owner_key)
    )
    await session.flush()


def _contacts_out(payload: dict[str, Any]) -> SkipTraceContactsOut:
    phones = payload.get("phones") or []
    emails = payload.get("emails") or []
    return SkipTraceContactsOut(phones=list(phones), emails=list(emails))


async def trace_owner(
    session: AsyncSession,
    provider: SkipTraceProvider,
    user_id: int,
    parcel_number: str,
) -> SkipTraceResultOut:
    subject = (await session.execute(_OWNER_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        raise ValidationError(f"Parcel {parcel_number} was not found.")
    if subject.owner_key is None:
        raise ValidationError("This parcel has no owner on record to trace.")
    owner_key = subject.owner_key

    cached = await _cached_payload(session, owner_key)
    if cached is not None and await _has_traced(session, user_id, owner_key):
        balance = await credit_balance(session, user_id)
        return SkipTraceResultOut(
            parcel_number=parcel_number,
            owner=subject.owner,
            contacts=_contacts_out(cached),
            credits_spent=0,
            credits_remaining=balance,
            cached=True,
        )

    if await credit_balance(session, user_id) < 1:
        raise QuotaExceededError("Not enough skip-trace credits. Buy a credit pack to continue.")

    if cached is not None:
        payload = cached
        provider_used = "cache"
    else:
        contacts = await provider.trace(
            owner=subject.owner, mailing_address=subject.mailing_address
        )
        payload = {"phones": contacts.phones, "emails": contacts.emails}
        await session.execute(
            insert(SkipTraceResult)
            .values(owner_key=owner_key, payload=payload, provider=provider.name)
            .on_conflict_do_update(
                index_elements=["owner_key"],
                set_={
                    "payload": payload,
                    "provider": provider.name,
                    "traced_at": datetime.now(UTC),
                },
            )
        )
        provider_used = provider.name

    await _burn(session, user_id, owner_key)
    balance = await credit_balance(session, user_id)
    return SkipTraceResultOut(
        parcel_number=parcel_number,
        owner=subject.owner,
        contacts=_contacts_out(payload),
        credits_spent=1,
        credits_remaining=balance,
        cached=provider_used == "cache",
    )
