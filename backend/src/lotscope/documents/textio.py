import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_DEED_BYTES = 25 * 1024 * 1024


def _pdf_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except (PyPdfError, ValueError, OSError):
        return ""


def extract_deed_text(data: bytes, content_type: str | None) -> str | None:
    if data[:5] == b"%PDF-" or content_type == "application/pdf":
        text = _pdf_text(data)
    else:
        text = data.decode("utf-8", errors="ignore").strip()
    return text or None
