"""The diligence checklist as a PDF, in the packet's clothes.

Same page furniture as the Sale Packet, because a buyer who has read one should not have
to learn a second document. The status column is the point of the page: a reader must be
able to see what is flagged, what is clear, and what we could not check, without reading
a line of prose.
"""

from fpdf.enums import XPos, YPos

from lotscope.diligence.schemas import DiligenceReport
from lotscope.reports.dossier import (
    _BRAND,
    _INK,
    _LINE,
    _MUTED,
    _Dossier,
    _s,
    _section,
)

_STATUS_COLOR = {
    "clear": (21, 128, 61),
    "flag": (185, 28, 28),
    "unverified": (180, 128, 9),
}
_STATUS_LABEL = {"clear": "CLEAR", "flag": "FLAG", "unverified": "UNVERIFIED"}

_CHECK_COLUMN = 62.0
_STATUS_COLUMN = 26.0


def _stamp(line: object) -> str:
    """When this line was true, and whether it was read live or from our copy."""
    fetched = getattr(line, "fetched_at", None)
    ingested = getattr(line, "ingested_at", None)
    if fetched is not None:
        return f"read live {fetched.strftime('%Y-%m-%d %H:%M')} UTC"
    if ingested is not None:
        return f"our copy, ingested {ingested.strftime('%Y-%m-%d')}"
    return "no as-of recorded"


def _header_block(pdf: _Dossier, report: DiligenceReport) -> None:
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_BRAND)
    pdf.cell(
        0,
        8,
        _s(f"Lot Diligence - {report.address or report.parcel_number}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        5,
        _s(
            f"Parcel {report.parcel_number} - {len(report.lines)} checks - "
            f"{report.flags} flagged, {report.unverified} unverified - computed "
            f"{report.computed_at.strftime('%Y-%m-%d %H:%M')} UTC"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(*_INK)


def _row(pdf: _Dossier, line: object) -> None:
    width = pdf.w - pdf.l_margin - pdf.r_margin
    evidence_width = width - _CHECK_COLUMN - _STATUS_COLUMN
    top = pdf.get_y()

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(_CHECK_COLUMN, 4.6, _s(getattr(line, "label", "")), align="L")
    label_bottom = pdf.get_y()

    status = str(getattr(line, "status", "unverified"))
    pdf.set_xy(pdf.l_margin + _CHECK_COLUMN, top)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_STATUS_COLOR.get(status, _MUTED))
    pdf.cell(_STATUS_COLUMN, 4.6, _s(_STATUS_LABEL.get(status, status.upper())))

    pdf.set_xy(pdf.l_margin + _CHECK_COLUMN + _STATUS_COLUMN, top)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(evidence_width, 4.2, _s(str(getattr(line, "evidence", ""))), align="L")

    pdf.set_x(pdf.l_margin + _CHECK_COLUMN + _STATUS_COLUMN)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_MUTED)
    source = str(getattr(line, "source", ""))
    url = getattr(line, "source_url", None)
    trail = f"{source} - {_stamp(line)}"
    pdf.multi_cell(evidence_width, 3.4, _s(trail), align="L")
    if url:
        pdf.set_x(pdf.l_margin + _CHECK_COLUMN + _STATUS_COLUMN)
        pdf.multi_cell(evidence_width, 3.4, _s(url), align="L")

    pdf.set_y(max(label_bottom, pdf.get_y()) + 1.5)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_text_color(*_INK)


def render_diligence_pdf(report: DiligenceReport) -> bytes:
    pdf = _Dossier(orientation="P", unit="mm", format="A4")
    pdf.running_title = f"Lot Diligence {report.parcel_number}"
    pdf.running_subtitle = report.address or ""
    pdf.footer_note = (
        "LotScope reads public records and is not legal, title or financial advice. "
        "This checklist does not replace a title search or a municipal lien letter."
    )
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    _header_block(pdf, report)
    for line in report.lines:
        _row(pdf, line)

    _section(pdf, "Before you close")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 4.4, _s(report.closing), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def diligence_filename(parcel_number: str) -> str:
    return f"lotscope-diligence-{parcel_number.replace(':', '-')}.pdf"
