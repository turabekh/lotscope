from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.appeal.models import AppealPacketEntitlement
from lotscope.appeal.schemas import AppealPacketStatus
from lotscope.core.errors import QuotaExceededError
from lotscope.skiptrace.service import appeal_packet_balance, spend_appeal_packet_credit

SOURCE_PURCHASE = "purchase"
SOURCE_GRANT = "grant"

_ENTITLEMENT_SQL = text(
    "SELECT source FROM appeal_packet "
    "WHERE user_id = :user_id AND parcel_number = :parcel_number "
    "ORDER BY created_at LIMIT 1"
)


async def entitlement_source(session: AsyncSession, user_id: int, parcel_number: str) -> str | None:
    value = await session.scalar(
        _ENTITLEMENT_SQL, {"user_id": user_id, "parcel_number": parcel_number}
    )
    return str(value) if value is not None else None


async def has_entitlement(session: AsyncSession, user_id: int, parcel_number: str) -> bool:
    return await entitlement_source(session, user_id, parcel_number) is not None


async def record_entitlement(
    session: AsyncSession, user_id: int, parcel_number: str, *, source: str, ref: str | None
) -> None:
    if await has_entitlement(session, user_id, parcel_number):
        return
    session.add(
        AppealPacketEntitlement(
            user_id=user_id, parcel_number=parcel_number, source=source, ref=ref
        )
    )
    await session.flush()


async def packet_status(
    session: AsyncSession, user_id: int, parcel_number: str
) -> AppealPacketStatus:
    source = await entitlement_source(session, user_id, parcel_number)
    balance = await appeal_packet_balance(session, user_id)
    return AppealPacketStatus(
        parcel_number=parcel_number,
        entitled=source is not None,
        source=source,
        packet_credits=balance,
    )


async def redeem_packet(
    session: AsyncSession, user_id: int, parcel_number: str
) -> AppealPacketStatus:
    if not await has_entitlement(session, user_id, parcel_number):
        if await appeal_packet_balance(session, user_id) < 1:
            raise QuotaExceededError(
                "No included assessment packets left this month. "
                "Purchase the Assessment Review Packet to continue."
            )
        await spend_appeal_packet_credit(session, user_id, ref=parcel_number)
        await record_entitlement(
            session, user_id, parcel_number, source=SOURCE_GRANT, ref=parcel_number
        )
    return await packet_status(session, user_id, parcel_number)
