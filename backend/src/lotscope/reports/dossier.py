from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from lotscope.assemblage.schemas import AssemblageResult
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.distress.schemas import DistressResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.verdict.schemas import VerdictResult

_BRAND = (15, 75, 168)
_INK = (31, 41, 51)
_MUTED = (107, 122, 141)
_LINE = (224, 230, 240)
_SEVERITY = {
    "high": (198, 40, 40),
    "medium": (239, 108, 0),
    "low": (120, 144, 156),
    "info": (2, 119, 189),
}
_STATUS_COLOR = {
    "pass": (46, 125, 50),
    "warn": (239, 108, 0),
    "fail": (198, 40, 40),
    "info": (120, 144, 156),
}
_STATUS_LABEL = {"pass": "OK", "warn": "CHECK", "fail": "ISSUE", "info": "INFO"}

_REPLACEMENTS = {
    "\u2014": "-",
    "\u2013": "-",
    "\u2192": "->",
    "\u2022": "-",
    "\u2248": "~",
    "\u00a9": "(c)",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
}


def _s(text: str | None) -> str:
    if not text:
        return ""
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _money(value: float | None) -> str:
    return f"${value:,.0f}" if value is not None else "-"


def _num(value: float | None, suffix: str = "") -> str:
    return f"{value:,.0f}{suffix}" if value is not None else "-"


class _Dossier(FPDF):
    def header(self) -> None:
        if self.page_no() != 1:
            return

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")


def _section(pdf: _Dossier, title: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_BRAND)
    pdf.cell(0, 6, _s(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1.5)


def _kv(pdf: _Dossier, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(48, 5.5, _s(label))
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5.5, _s(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _tag(pdf: _Dossier, text: str, color: tuple[int, int, int]) -> None:
    pdf.set_font("Helvetica", "B", 8)
    width = pdf.get_string_width(_s(text)) + 6
    pdf.set_fill_color(*color)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(width, 5.5, _s(text), align="C", fill=True)
    pdf.cell(2, 5.5, "")


def render_dossier_pdf(
    *,
    detail: ParcelDetail,
    verdict: VerdictResult | None,
    assemblage: AssemblageResult | None,
    distress: DistressResult | None,
    checklist: ParcelChecklist | None = None,
    generated_at: datetime,
    disclaimer: str,
) -> bytes:
    pdf = _Dossier(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    pdf.set_fill_color(*_BRAND)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_xy(16, 7)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(210, 225, 245)
    pdf.cell(0, 4, "LOTSCOPE PHL - PARCEL DOSSIER", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, _s(detail.address or detail.parcel_number))
    pdf.set_y(30)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5, _s(f"Parcel {detail.parcel_number}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    _tag(pdf, detail.base_zoning_code or "No zoning", _BRAND)
    if detail.is_vacant:
        _tag(pdf, "VACANT", (245, 158, 11))
    if detail.is_city_owned:
        _tag(pdf, "CITY-OWNED", (216, 67, 21))
    pdf.ln(8)

    if verdict is not None:
        _section(pdf, "Parcel verdict")
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*_BRAND)
        pdf.cell(26, 10, str(round(verdict.opportunity_score)))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 4.5, _s(verdict.summary or "Opportunity score (0-100)."))
        pdf.ln(2)
        _kv(pdf, "By-right units", _num(verdict.by_right_units))
        _kv(pdf, "Max height", _num(verdict.max_height_ft, " ft"))
        _kv(pdf, "Buildable area", _num(verdict.buildable_area_sqft, " sq ft"))
        low, high = verdict.value_estimate_low, verdict.value_estimate_high
        value = f"{_money(low)} - {_money(high)}" if low is not None else "Not enough comps"
        _kv(pdf, "Estimated land value", value)
        _kv(pdf, "vs. assessment", _money(verdict.assessment_market_gap))

        if verdict.max_allowable_offer is not None:
            _section(pdf, "Deal analysis")
            if verdict.deal_score is not None:
                color = (27, 94, 32) if verdict.is_underpriced else _BRAND
                _tag(pdf, f"DEAL SCORE {round(verdict.deal_score)}/100", color)
                if verdict.is_underpriced:
                    _tag(pdf, "UNDERPRICED", (27, 94, 32))
                pdf.ln(8)
            _kv(pdf, "Max allowable offer", _money(verdict.max_allowable_offer))
            _kv(pdf, "After-build value (ARV)", _money(verdict.arv))
            _kv(pdf, "Estimated profit", _money(verdict.est_profit))
            margin = f"{verdict.est_margin * 100:.1f}%" if verdict.est_margin is not None else "-"
            _kv(pdf, "Estimated margin", margin)

        _section(pdf, "Risk")
        score = "-" if verdict.risk_score is None else f"{round(verdict.risk_score)}/100"
        _kv(pdf, "Risk score", score)
        if verdict.risk_flags:
            for flag in verdict.risk_flags:
                severity = str(flag.get("severity", "info"))
                color = _SEVERITY.get(severity, _MUTED)
                pdf.set_fill_color(*color)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 7)
                pdf.cell(16, 4.5, _s(severity.upper()), align="C", fill=True)
                pdf.cell(2, 4.5, "")
                pdf.set_text_color(*_INK)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.cell(
                    0, 4.5, _s(str(flag.get("label", ""))), new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
                pdf.set_x(34)
                pdf.set_text_color(*_MUTED)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 4, _s(str(flag.get("detail", ""))))
        else:
            pdf.set_text_color(*_MUTED)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 5, "No major risk flags.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if checklist is not None and checklist.items:
        _section(pdf, "Due-diligence checklist")
        summary = checklist.summary
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_MUTED)
        pdf.cell(
            0,
            5,
            _s(
                f"{summary.passed} clear, {summary.warnings} to check, {summary.failures} issue(s)."
            ),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        pdf.ln(1)
        for item in checklist.items:
            color = _STATUS_COLOR.get(item.status, _MUTED)
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(16, 4.5, _s(_STATUS_LABEL.get(item.status, "")), align="C", fill=True)
            pdf.cell(2, 4.5, "")
            pdf.set_text_color(*_INK)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.cell(0, 4.5, _s(item.category), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(34)
            pdf.set_text_color(*_MUTED)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 4, _s(item.detail))

    _section(pdf, "Property")
    _kv(pdf, "Owner", detail.owner or "-")
    _kv(pdf, "Land use", detail.land_use or "-")
    _kv(pdf, "Lot area", _num(detail.lot_area_sqft, " sq ft"))
    _kv(pdf, "Frontage x depth", f"{_num(detail.frontage_ft)} x {_num(detail.depth_ft)} ft")
    _kv(pdf, "Assessed value", _money(detail.market_value))
    _kv(
        pdf,
        "Land / improvement",
        f"{_money(detail.land_value)} / {_money(detail.improvement_value)}",
    )

    if assemblage is not None and assemblage.neighbors:
        _section(pdf, "Assemblage")
        _kv(pdf, "Potential", assemblage.potential.replace("_", " ").title())
        _kv(pdf, "Buyable neighbors", str(assemblage.summary.candidate_count))
        _kv(pdf, "Combined land", _num(assemblage.summary.combined_lot_area_sqft, " sq ft"))
        cur = assemblage.summary.by_right_units_current
        combined = assemblage.summary.by_right_units_combined
        if cur is not None and combined is not None and combined > cur:
            _kv(pdf, "Units (assembled)", f"{cur} -> {combined}")

    if distress is not None and distress.factors:
        _section(pdf, "Motivated-seller distress")
        _kv(pdf, "Distress score", f"{distress.score}/100 ({distress.tier})")
        for factor in distress.factors:
            pdf.set_text_color(*_MUTED)
            pdf.set_font("Helvetica", "", 8.5)
            pdf.cell(0, 4.5, _s(f"- {factor.label}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(6)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_MUTED)
    stamp = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    pdf.multi_cell(0, 3.6, _s(f"Generated {stamp}. {disclaimer}"))

    return bytes(pdf.output())


def dossier_filename(parcel_number: str) -> str:
    return f"lotscope-dossier-{parcel_number}.pdf"
