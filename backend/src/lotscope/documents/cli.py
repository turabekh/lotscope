import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from lotscope.ai.client import AnthropicGenerator
from lotscope.ai.embeddings import VoyageEmbedder
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.documents.models import DeedDocument
from lotscope.documents.ocr import PaddleOcrEngine
from lotscope.documents.pipeline import process_deed_text
from lotscope.documents.storage import LocalBlobStore


async def _process(parcel_number: str, path: str) -> int:
    settings = get_settings()
    configure_logging(settings)
    logger = get_logger("documents")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    with open(path, "rb") as handle:
        data = handle.read()

    blob_store = LocalBlobStore(settings.deed_blob_root)
    blob_key = f"{parcel_number}/{path.rsplit('/', 1)[-1]}"
    await blob_store.put(blob_key, data)

    ocr = PaddleOcrEngine()
    text = await ocr.extract_text(data)

    embedder = VoyageEmbedder(settings)
    generator = AnthropicGenerator(settings)

    async with session_factory() as session:
        existing = (
            await session.execute(
                select(DeedDocument).where(DeedDocument.blob_key == blob_key)
            )
        ).scalar_one_or_none()
        deed = existing or DeedDocument(parcel_number=parcel_number)
        deed.blob_key = blob_key
        deed.external_id = deed.external_id or blob_key
        deed.source = "manual"
        deed.ocr_status = "ocr_done"
        deed.recording_date = deed.recording_date or datetime.now(UTC).date()
        session.add(deed)
        await session.flush()
        count = await process_deed_text(
            session, deed, text, embedder=embedder, generator=generator
        )
        await session.commit()
    await engine.dispose()
    logger.info("deed_processed", parcel_number=parcel_number, restrictions=count)
    return count


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m lotscope.documents.cli <parcel_number> <deed_file>")
    asyncio.run(_process(sys.argv[1], sys.argv[2]))


if __name__ == "__main__":
    main()
