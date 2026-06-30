from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.documents.links import philadox_document_url
from lotscope.documents.models import DeedDocument, DeedRestriction
from lotscope.documents.schemas import (
    DeedRestrictionItem,
    DeedRestrictionsResponse,
    RecordedDeedItem,
)

_RECORDED_DEEDS_SQL = text(
    "SELECT s.document_id, s.document_type, s.sale_date, s.grantor, s.grantee, s.sale_price, "
    "(dd.id IS NOT NULL) AS analyzed "
    "FROM sale s "
    "LEFT JOIN deed_document dd "
    "ON dd.parcel_number = s.parcel_number AND dd.external_id = s.document_id "
    "WHERE s.parcel_number = :parcel_number AND s.document_id IS NOT NULL "
    "ORDER BY s.sale_date DESC NULLS LAST, s.document_id"
)


def _as_float(value: Any) -> float | None:
    return float(value) if value is not None else None


async def get_deed_restrictions(
    session: AsyncSession, parcel_number: str, *, record_url_template: str
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
    deed_rows = (await session.execute(_RECORDED_DEEDS_SQL, {"parcel_number": parcel_number})).all()
    deeds = [
        RecordedDeedItem(
            document_id=row.document_id,
            document_type=row.document_type,
            recording_date=row.sale_date,
            grantor=row.grantor,
            grantee=row.grantee,
            sale_price=_as_float(row.sale_price),
            analyzed=row.analyzed,
            record_url=philadox_document_url(record_url_template, row.document_id),
        )
        for row in deed_rows
    ]
    return DeedRestrictionsResponse(
        parcel_number=parcel_number,
        count=len(restrictions),
        restrictions=restrictions,
        deeds=deeds,
    )
