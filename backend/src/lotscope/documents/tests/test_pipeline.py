from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.models import EMBEDDING_DIMENSIONS
from lotscope.ai.service import ask_the_parcel
from lotscope.documents.models import DeedDocument
from lotscope.documents.pipeline import process_deed_text
from lotscope.documents.service import get_deed_restrictions

pytestmark = pytest.mark.integration

_URL_TEMPLATE = "https://records.test/doc/{document_id}"


def _embedding(*leading: float) -> list[float]:
    values = list(leading)
    return values + [0.0] * (EMBEDDING_DIMENSIONS - len(values))


class _FakeEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [_embedding(1.0, 0.0) for _ in texts]


class _FakeGenerator:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.captured_user: str | None = None

    async def generate(self, *, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.captured_user = user
        return self._payload


_EXTRACTION = {
    "has_restrictions": True,
    "restrictions": [
        {
            "kind": "use_restriction",
            "text": "No multi-family dwellings permitted on the lot.",
            "citation": "Paragraph 3",
            "confidence": "high",
        }
    ],
}


async def _seed_deed(session: AsyncSession) -> DeedDocument:
    await session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000001')"))
    deed = DeedDocument(
        parcel_number="000000001",
        external_id="DEED-1",
        document_type="DEED",
        ocr_status="ocr_done",
    )
    session.add(deed)
    await session.flush()
    return deed


async def test_process_deed_text_persists_restrictions_and_chunks(db_session: AsyncSession) -> None:
    deed = await _seed_deed(db_session)
    count = await process_deed_text(
        db_session,
        deed,
        "This deed restricts the property. No multi-family dwellings permitted.",
        embedder=_FakeEmbedder(),
        generator=_FakeGenerator(_EXTRACTION),
    )
    assert count == 1
    assert deed.ocr_status == "extracted"

    restrictions = await get_deed_restrictions(
        db_session, "000000001", record_url_template=_URL_TEMPLATE
    )
    assert restrictions.count == 1
    assert restrictions.restrictions[0].kind == "use_restriction"
    assert restrictions.restrictions[0].document_type == "DEED"

    doc_count = await db_session.scalar(
        text(
            "SELECT count(*) FROM document WHERE source = 'deed' "
            "AND doc_metadata->>'parcel_number' = '000000001'"
        )
    )
    assert doc_count == 1


class _FakeBlobStore:
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> str:
        self.saved[key] = data
        return key

    async def get(self, key: str) -> bytes:
        return self.saved[key]


async def test_analyze_uploaded_deed_extracts_and_marks_analyzed(db_session: AsyncSession) -> None:
    from lotscope.documents.service import analyze_uploaded_deed

    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000060')"))
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date) "
            "VALUES ('000000060', '53999001', 'DEED', '2023-02-02')"
        )
    )
    await db_session.flush()

    blob = _FakeBlobStore()
    response = await analyze_uploaded_deed(
        db_session,
        "000000060",
        "53999001",
        b"No multi-family dwellings permitted on the lot.",
        "text/plain",
        embedder=_FakeEmbedder(),
        generator=_FakeGenerator(_EXTRACTION),
        blob_store=blob,
        record_url_template=_URL_TEMPLATE,
    )
    assert response.count == 1
    assert response.restrictions[0].kind == "use_restriction"
    analyzed = next(d for d in response.deeds if d.document_id == "53999001")
    assert analyzed.analyzed is True
    assert blob.saved


async def test_analyze_uploaded_deed_rejects_unknown_document(db_session: AsyncSession) -> None:
    from lotscope.core.errors import NotFoundError
    from lotscope.documents.service import analyze_uploaded_deed

    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000061')"))
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await analyze_uploaded_deed(
            db_session,
            "000000061",
            "99999999",
            b"text",
            "text/plain",
            embedder=_FakeEmbedder(),
            generator=_FakeGenerator(_EXTRACTION),
            blob_store=_FakeBlobStore(),
            record_url_template=_URL_TEMPLATE,
        )


async def test_deed_index_lists_recorded_deeds_with_links(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000050')"))
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, "
            "grantor, grantee, sale_price) VALUES "
            "('000000050', '53772373', 'DEED', '2021-05-01', 'SMITH JOHN', 'DOE JANE', 250000)"
        )
    )
    await db_session.flush()

    result = await get_deed_restrictions(db_session, "000000050", record_url_template=_URL_TEMPLATE)
    assert len(result.deeds) == 1
    deed = result.deeds[0]
    assert deed.document_id == "53772373"
    assert deed.document_type == "DEED"
    assert deed.analyzed is False
    assert deed.record_url == "https://records.test/doc/53772373"


async def test_process_deed_text_is_idempotent_on_restrictions(db_session: AsyncSession) -> None:
    deed = await _seed_deed(db_session)
    for _ in range(2):
        await process_deed_text(
            db_session,
            deed,
            "No multi-family dwellings permitted.",
            embedder=_FakeEmbedder(),
            generator=_FakeGenerator(_EXTRACTION),
        )
    restrictions = await get_deed_restrictions(
        db_session, "000000001", record_url_template=_URL_TEMPLATE
    )
    assert restrictions.count == 1


async def test_ask_the_parcel_includes_deed_context(db_session: AsyncSession) -> None:
    deed = await _seed_deed(db_session)
    await process_deed_text(
        db_session,
        deed,
        "No multi-family dwellings permitted on the lot.",
        embedder=_FakeEmbedder(),
        generator=_FakeGenerator(_EXTRACTION),
    )

    generator = _FakeGenerator(
        {
            "answer": "The deed forbids multi-family use.",
            "citations": [{"source": "deed", "section": "DEED-1"}],
            "confidence": "high",
        }
    )
    answer = await ask_the_parcel(
        db_session,
        "000000001",
        "Are there deed restrictions?",
        embedder=_FakeEmbedder(),
        generator=generator,
    )
    assert answer is not None
    assert generator.captured_user is not None
    assert "multi-family" in generator.captured_user.lower()
