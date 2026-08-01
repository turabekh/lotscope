from datetime import datetime

from fpdf.enums import XPos, YPos

from lotscope.assessment.schemas import AssessmentResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.reports.dossier import (
    _BRAND,
    _INK,
    _LINE,
    _MUTED,
    _Dossier,
    _kv,
    _money,
    _num,
    _s,
    _section,
    _tag,
)
from lotscope.valuation.schemas import ValuationResult

_STATUS_STYLE: dict[str, tuple[str, tuple[int, int, int]]] = {
    "over_assessed": ("OVER-ASSESSED", (27, 94, 32)),
    "fairly_assessed": ("FAIRLY ASSESSED", (120, 144, 156)),
    "under_assessed": ("UNDER-ASSESSED", (198, 40, 40)),
    "unknown": ("INSUFFICIENT DATA", (120, 144, 156)),
}

_APPEAL_POINTERS = (
    "File a First Level Review (FLR) with the Office of Property Assessment (OPA) using the "
    "form mailed with your assessment notice, or a formal appeal with the Board of Revision of "
    "Taxes (BRT).",
    "BRT appeals for the following tax year are generally due by the first Monday in October; "
    "First Level Review windows are shorter and tied to the notice date.",
    "Confirm current deadlines and forms at phila.gov before filing. Bring this packet's comps "
    "and market estimate as your evidence of value.",
)


def _comp_table(pdf: _Dossier, valuation: ValuationResult) -> None:
    headers = [("Address", 62), ("Dist (ft)", 22), ("Sold", 24), ("Price", 26), ("$/sqft", 22)]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_MUTED)
    for label, width in headers:
        pdf.cell(width, 5, _s(label))
    pdf.ln(5)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_INK)
    for comp in valuation.comps:
        sold = comp.sale_date.strftime("%Y-%m") if comp.sale_date is not None else "-"
        row = [
            (_s(comp.address or comp.parcel_number)[:34], 62),
            (_num(comp.distance_ft), 22),
            (sold, 24),
            (_money(comp.sale_price), 26),
            (_num(comp.price_per_sqft), 22),
        ]
        for value, width in row:
            pdf.cell(width, 5, value)
        pdf.ln(5)


def render_appeal_packet_pdf(
    *,
    detail: ParcelDetail,
    assessment: AssessmentResult,
    valuation: ValuationResult | None,
    generated_at: datetime,
) -> bytes:
    pdf = _Dossier(format="A4")
    pdf.running_title = _s(detail.address or detail.parcel_number)
    pdf.running_subtitle = _s(f"Parcel {detail.parcel_number}")
    pdf.footer_note = _s("Assessment review packet - prepared from public city data")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(16, 16, 16)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_fill_color(*_BRAND)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_xy(16, 7)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(210, 225, 245)
    pdf.cell(0, 4, "LOTSCOPE PHL - ASSESSMENT REVIEW PACKET", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, _s(detail.address or detail.parcel_number))
    pdf.set_y(30)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    stamp = generated_at.strftime("%d %B %Y")
    pdf.cell(
        0,
        5,
        _s(f"Parcel {detail.parcel_number}   |   Prepared {stamp}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)
    label, color = _STATUS_STYLE.get(assessment.status, _STATUS_STYLE["unknown"])
    _tag(pdf, label, color)
    pdf.ln(9)

    _section(pdf, "Assessment summary")
    _kv(pdf, "Assessed market value", _money(assessment.assessed_market_value))
    estimate = assessment.market_estimate
    band = (
        f"{_money(assessment.market_low)} - {_money(assessment.market_high)}"
        if assessment.market_low is not None
        else "-"
    )
    _kv(pdf, "Modeled market value", _money(estimate))
    _kv(pdf, "Market value range", band)
    if assessment.gap_pct is not None:
        _kv(pdf, "Gap", f"{_money(assessment.gap)} ({assessment.gap_pct:+.0%})")
    _kv(pdf, "Over-assessed amount", _money(assessment.over_assessed_amount))
    _kv(pdf, "Estimated annual tax savings", _money(assessment.estimated_annual_tax_savings))
    _kv(pdf, "Confidence", assessment.confidence.title())
    for reason in assessment.reasons:
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 4.2, _s(reason), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _section(pdf, "Comparable sales")
    if valuation is not None and valuation.comps:
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            0,
            5,
            _s(f"{valuation.comp_count} recorded sale(s) within the search radius."),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)
        _comp_table(pdf, valuation)
    else:
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            0,
            5,
            "Not enough recorded comparable sales to model a market value.",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )

    _section(pdf, "How to appeal")
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_INK)
    for pointer in _APPEAL_POINTERS:
        pdf.multi_cell(0, 4.4, _s(f"- {pointer}"), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(0.5)

    pdf.ln(4)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_MUTED)
    stamp = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    pdf.multi_cell(
        0,
        3.6,
        _s(f"Generated {stamp}. {assessment.disclaimer}"),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


def appeal_packet_filename(parcel_number: str) -> str:
    return f"lotscope-assessment-review-{parcel_number.replace(':', '-')}.pdf"
