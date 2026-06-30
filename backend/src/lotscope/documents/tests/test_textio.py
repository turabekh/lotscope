from fpdf import FPDF

from lotscope.documents.textio import extract_deed_text


def _text_pdf(body: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, body)
    return bytes(pdf.output())


def test_extracts_plain_text() -> None:
    text = extract_deed_text(b"No multi-family dwellings permitted.", "text/plain")
    assert text == "No multi-family dwellings permitted."


def test_extracts_text_layer_pdf() -> None:
    data = _text_pdf("No multi-family dwellings permitted on these premises.")
    text = extract_deed_text(data, "application/pdf")
    assert text is not None
    assert "multi-family" in text


def test_empty_or_unextractable_returns_none() -> None:
    assert extract_deed_text(b"", "text/plain") is None
    assert extract_deed_text(b"%PDF-1.4 not really a pdf", "application/pdf") is None
