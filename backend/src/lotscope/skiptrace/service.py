from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.core.errors import ValidationError
from lotscope.skiptrace.models import SkipTraceResult
from lotscope.skiptrace.provider import SkipTraceProvider
from lotscope.skiptrace.schemas import (
    SkipTraceContactsOut,
    SkipTraceResultOut,
)

CACHE_TTL_DAYS = 30

_OWNER_SQL = text(
    "SELECT owner, owner_key, mailing_address, market_code "
    "FROM parcel WHERE parcel_number = :parcel_number"
)
_BALANCE_SQL = text(
    "SELECT coalesce(sum(delta), 0) FROM credit_ledger "
    "WHERE user_id = :user_id AND reason = ANY(:reasons)"
)
_HAS_TRACED_SQL = text(
    "SELECT EXISTS (SELECT 1 FROM credit_ledger "
    "WHERE user_id = :user_id AND reason = :reason AND ref = :owner_key)"
)


async def _cached_payload(
    session: AsyncSession, owner_key: str, ttl_days: int
) -> dict[str, Any] | None:
    cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
    result = await session.get(SkipTraceResult, owner_key)
    if result is None or result.traced_at < cutoff:
        return None
    return result.payload


def _contacts_out(payload: dict[str, Any]) -> SkipTraceContactsOut:
    phones = payload.get("phones") or []
    emails = payload.get("emails") or []
    return SkipTraceContactsOut(phones=list(phones), emails=list(emails))


async def trace_owner(
    session: AsyncSession,
    provider: SkipTraceProvider,
    user_id: int,
    parcel_number: str,
    *,
    ttl_days: int = CACHE_TTL_DAYS,
) -> SkipTraceResultOut:
    subject = (await session.execute(_OWNER_SQL, {"parcel_number": parcel_number})).one_or_none()
    if subject is None:
        raise ValidationError(f"Parcel {parcel_number} was not found.")
    if subject.owner_key is None:
        raise ValidationError("This parcel has no owner on record to trace.")
    owner_key = subject.owner_key

    cached = await _cached_payload(session, owner_key, ttl_days)
    if cached is not None:
        return SkipTraceResultOut(
            parcel_number=parcel_number,
            owner=subject.owner,
            contacts=_contacts_out(cached),
            cached=True,
        )

    contacts = await provider.trace(owner=subject.owner, mailing_address=subject.mailing_address)
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

    return SkipTraceResultOut(
        parcel_number=parcel_number,
        owner=subject.owner,
        contacts=_contacts_out(payload),
        cached=False,
    )
