from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.documents.models import DeedDocument, DeedRestriction
from lotscope.documents.schemas import DeedRestrictionItem, DeedRestrictionsResponse


async def get_deed_restrictions(
    session: AsyncSession, parcel_number: str
) -> DeedRestrictionsResponse:
    rows = (
        await session.execute(
            select(DeedRestriction, DeedDocument)
            .join(DeedDocument, DeedDocument.id == DeedRestriction.deed_document_id)
            .where(DeedRestriction.parcel_number == parcel_number)
            .order_by(DeedRestriction.confidence, DeedRestriction.id)
        )
    ).all()
    restrictions = [
        DeedRestrictionItem(
            kind=restriction.kind,
            text=restriction.text,
            citation=restriction.citation,
            confidence=restriction.confidence,
            document_type=deed.document_type,
            recording_date=deed.recording_date,
        )
        for restriction, deed in rows
    ]
    return DeedRestrictionsResponse(
        parcel_number=parcel_number,
        count=len(restrictions),
        restrictions=restrictions,
    )
