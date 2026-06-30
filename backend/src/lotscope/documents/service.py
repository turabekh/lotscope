from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.core.errors import NotFoundError, ValidationError
from lotscope.documents.links import philadox_document_url
from lotscope.documents.models import DeedDocument, DeedRestriction
from lotscope.documents.pipeline import process_deed_text
from lotscope.documents.schemas import (
    DeedRestrictionItem,
    DeedRestrictionsResponse,
    RecordedDeedItem,
)
from lotscope.documents.storage import BlobStore
from lotscope.documents.textio import MAX_DEED_BYTES, extract_deed_text

_RECORDED_DEED_SQL = text(
    "SELECT document_type, sale_date FROM sale "
    "WHERE parcel_number = :parcel_number AND document_id = :document_id LIMIT 1"
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


async def analyze_uploaded_deed(
    session: AsyncSession,
    parcel_number: str,
    document_id: str,
    data: bytes,
    content_type: str | None,
    *,
    embedder: Embedder,
    generator: StructuredGenerator,
    blob_store: BlobStore,
    record_url_template: str,
) -> DeedRestrictionsResponse:
    if not data:
        raise ValidationError("The uploaded deed file is empty.")
    if len(data) > MAX_DEED_BYTES:
        raise ValidationError("The uploaded deed file is too large.")

    recorded = (
        await session.execute(
            _RECORDED_DEED_SQL, {"parcel_number": parcel_number, "document_id": document_id}
        )
    ).one_or_none()
    if recorded is None:
        raise NotFoundError(
            f"No recorded document {document_id} is on file for parcel {parcel_number}."
        )

    deed_text = extract_deed_text(data, content_type)
    if deed_text is None:
        raise ValidationError(
            "Could not extract text from the uploaded file. Scanned-image PDFs need OCR, which is "
            "not enabled here — upload a text-based PDF or a .txt transcript."
        )

    blob_key = f"{parcel_number}/{document_id}"
    await blob_store.put(blob_key, data)

    deed = (
        await session.execute(
            select(DeedDocument).where(
                DeedDocument.parcel_number == parcel_number,
                DeedDocument.external_id == document_id,
            )
        )
    ).scalar_one_or_none()
    if deed is None:
        deed = DeedDocument(parcel_number=parcel_number, external_id=document_id)
        session.add(deed)
    deed.document_type = recorded.document_type
    deed.recording_date = recorded.sale_date
    deed.blob_key = blob_key
    deed.source = "upload"
    deed.ocr_status = "ocr_done"
    await session.flush()

    await process_deed_text(session, deed, deed_text, embedder=embedder, generator=generator)
    await session.commit()
    return await get_deed_restrictions(
        session, parcel_number, record_url_template=record_url_template
    )
