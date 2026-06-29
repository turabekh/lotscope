from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.corpus import chunk_text
from lotscope.ai.embeddings import Embedder
from lotscope.ai.retrieval import add_document
from lotscope.documents.extraction import extract_restrictions
from lotscope.documents.models import DeedDocument, DeedRestriction

DEED_SOURCE = "deed"


async def process_deed_text(
    session: AsyncSession,
    deed: DeedDocument,
    text: str,
    *,
    embedder: Embedder,
    generator: StructuredGenerator,
) -> int:
    extraction = await extract_restrictions(generator, text)

    await session.execute(
        delete(DeedRestriction).where(DeedRestriction.deed_document_id == deed.id)
    )
    for restriction in extraction.restrictions:
        session.add(
            DeedRestriction(
                deed_document_id=deed.id,
                parcel_number=deed.parcel_number,
                kind=restriction.kind,
                text=restriction.text,
                citation=restriction.citation,
                confidence=restriction.confidence,
            )
        )

    chunks = chunk_text(text)
    if chunks:
        embeddings = await embedder.embed(chunks)
        metadata = {
            "parcel_number": deed.parcel_number,
            "deed_document_id": deed.id,
        }
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            await add_document(
                session,
                source=DEED_SOURCE,
                section=deed.external_id,
                title=deed.document_type,
                content=chunk,
                embedding=embedding,
                metadata=metadata,
            )

    deed.ocr_status = "extracted"
    await session.flush()
    return len(extraction.restrictions)
