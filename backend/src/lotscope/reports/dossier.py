from datetime import datetime
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from lotscope.ai.schemas import ParcelReportResult
from lotscope.assemblage.schemas import AssemblageResult
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.distress.schemas import DistressResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.verdict.schemas import VerdictResult
from lotscope.zoning.posture import BuildabilityPosture, resolve_posture, unit_claim
from lotscope.zoning.schemas import BuildabilityResult

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
    "potential_issue": (239, 108, 0),
    "fail": (198, 40, 40),
    "not_evaluated": (120, 144, 156),
    "not_applicable": (144, 164, 174),
}
_STATUS_LABEL = {
    "pass": "OK",
    "potential_issue": "CHECK",
    "fail": "ISSUE",
    "not_evaluated": "NOT CHECKED",
    "not_applicable": "N/A",
}
_CONFIDENCE_COLOR = {
    "high": (46, 125, 50),
    "medium": (239, 108, 0),
    "low": (120, 144, 156),
}

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
    if value is None:
        return "-"
    if value < 0:
        return f"-${abs(value):,.0f}"
    return f"${value:,.0f}"


def _num(value: float | None, suffix: str = "") -> str:
    return f"{value:,.0f}{suffix}" if value is not None else "-"


class _Dossier(FPDF):
    running_title: str = ""
    running_subtitle: str = ""
    footer_note: str = ""

    def header(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(8)
        half = (self.w - self.l_margin - self.r_margin) / 2
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_BRAND)
        self.cell(half, 4, _s(self.running_title))
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_MUTED)
        self.cell(
            half, 4, _s(self.running_subtitle), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        self.ln(1)
        self.set_draw_color(*_LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.set_y(20)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_draw_color(*_LINE)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1)
        half = (self.w - self.l_margin - self.r_margin) / 2
        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(*_MUTED)
        self.cell(half * 1.4, 4, _s(self.footer_note))
        self.cell(half * 0.6, 4, f"Page {self.page_no()} of {{nb}}", align="R")


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


def _note(pdf: _Dossier, text: str) -> None:
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 3.8, _s(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)


def _market_label(detail: ParcelDetail) -> str:
    return f"Market {detail.market_code.upper()}"


def _summary_band(pdf: _Dossier, verdict: VerdictResult) -> None:
    low, high = verdict.value_estimate_low, verdict.value_estimate_high
    land = f"{_money(low)} - {_money(high)}" if low is not None else "Not enough comps"
    if verdict.max_allowable_offer is not None and verdict.max_allowable_offer > 0:
        deal_label, deal_value = "Max allowable offer", _money(verdict.max_allowable_offer)
    elif verdict.arv is not None:
        deal_label, deal_value = "After-build value", _money(verdict.arv)
    else:
        deal_label, deal_value = "Deal model", "Not evaluated"
    risk = "-" if verdict.risk_score is None else f"{round(verdict.risk_score)}/100"

    cells = [
        ("Opportunity score", f"{round(verdict.opportunity_score)}/100"),
        ("Estimated land value", land),
        (deal_label, deal_value),
        ("Risk score", risk),
    ]
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    width = usable / len(cells)
    top = pdf.get_y()
    pdf.set_draw_color(*_LINE)
    pdf.set_fill_color(247, 249, 252)
    pdf.rect(pdf.l_margin, top, usable, 17, style="DF")
    for index, (label, value) in enumerate(cells):
        x = pdf.l_margin + index * width
        if index:
            pdf.line(x, top + 2, x, top + 15)
        pdf.set_xy(x + 3, top + 3)
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*_MUTED)
        pdf.cell(width - 6, 3.5, _s(label.upper()), new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_x(x + 3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_INK)
        pdf.cell(width - 6, 6, _s(value))
    pdf.set_y(top + 21)


def _source_names(entry: dict[str, Any]) -> str:
    raw = entry.get("sources")
    if not isinstance(raw, list):
        return "-"
    names: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("source", "")).strip()
        if not name:
            continue
        version = item.get("version") or item.get("code")
        names.append(f"{name} ({version})" if version else name)
    return ", ".join(dict.fromkeys(names)) or "-"


def _sources(pdf: _Dossier, verdict: VerdictResult) -> None:
    _section(pdf, "Data sources")
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        3.8,
        _s(
            "Every figure above is computed from the datasets below. City data is published "
            "as-is; verify against the recorded document before relying on a result."
        ),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(1)
    for entry in verdict.sources:
        dimension = str(entry.get("dimension", "")).replace("_", " ").title() or "-"
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(34, 4.5, _s(dimension))
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(
            0, 4.5, _s(_source_names(entry)), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*_INK)
    pdf.cell(34, 4.5, "Verdict")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    computed = verdict.computed_at.strftime("%d %B %Y")
    pdf.multi_cell(
        0,
        4.5,
        _s(f"{verdict.verdict_version}, computed {computed}"),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _report_posture(
    verdict: VerdictResult, buildability: BuildabilityResult | None
) -> BuildabilityPosture:
    return resolve_posture(
        requires_master_plan=(
            buildability.requires_master_plan if buildability is not None else False
        ),
        can_build_by_right=verdict.can_build_by_right,
        needs_variance=verdict.needs_variance,
    )


def _buildability_reasons(pdf: _Dossier, buildability: BuildabilityResult | None) -> None:
    if buildability is None or not buildability.reasons:
        return
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 4, "HOW THESE FIGURES WERE REACHED", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    for reason in buildability.reasons:
        pdf.set_x(pdf.l_margin + 2)
        pdf.set_text_color(*_MUTED)
        pdf.cell(3, 4.2, "-")
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 4.2, _s(reason), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


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
    buildability: BuildabilityResult | None = None,
    assemblage: AssemblageResult | None,
    distress: DistressResult | None,
    checklist: ParcelChecklist | None = None,
    report: ParcelReportResult | None = None,
    generated_at: datetime,
    disclaimer: str,
) -> bytes:
    title = detail.address or detail.parcel_number
    stamp = generated_at.strftime("%d %B %Y, %H:%M UTC")

    pdf = _Dossier(format="A4")
    pdf.running_title = _s(title)
    pdf.running_subtitle = _s(f"Parcel {detail.parcel_number}")
    pdf.footer_note = _s("LotScope - informational only, not legal, financial or property advice")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(16, 16, 16)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_fill_color(*_BRAND)
    pdf.rect(0, 0, pdf.w, 30, style="F")
    pdf.set_xy(16, 7)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(190, 212, 240)
    pdf.cell(0, 4, "PARCEL DOSSIER", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, _s(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(190, 212, 240)
    meta = f"Parcel {detail.parcel_number}   |   {_market_label(detail)}   |   Generated {stamp}"
    pdf.cell(0, 4, _s(meta))
    pdf.set_y(36)

    _tag(pdf, detail.base_zoning_code or "No zoning", _BRAND)
    if detail.is_vacant:
        _tag(pdf, "VACANT", (245, 158, 11))
    if detail.is_city_owned:
        _tag(pdf, "CITY-OWNED", (216, 67, 21))
    pdf.ln(9)

    if verdict is not None:
        _summary_band(pdf, verdict)

    if verdict is not None:
        _section(pdf, "Parcel verdict")
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*_BRAND)
        pdf.cell(26, 10, str(round(verdict.opportunity_score)))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 4.5, _s(verdict.summary or "Opportunity score (0-100)."), align="L")
        pdf.ln(2)
        units = unit_claim(
            _report_posture(verdict, buildability),
            verdict.by_right_units,
        )
        _kv(pdf, units.label, units.value)
        _kv(pdf, "Max height", _num(verdict.max_height_ft, " ft"))
        _kv(pdf, "Buildable area", _num(verdict.buildable_area_sqft, " sq ft"))
        low, high = verdict.value_estimate_low, verdict.value_estimate_high
        band = verdict.value_confidence_band
        suffix = f" ({band} confidence)" if low is not None and band is not None else ""
        value = f"{_money(low)} - {_money(high)}{suffix}" if low is not None else "Not enough comps"
        _kv(pdf, "Estimated land value", value)
        _note(pdf, verdict.value_support_note)
        _kv(pdf, "vs. assessment", _money(verdict.assessment_market_gap))
        _buildability_reasons(pdf, buildability)

        if verdict.max_allowable_offer is not None and verdict.max_allowable_offer <= 0:
            _section(pdf, "Deal analysis")
            _tag(pdf, "NEW BUILD NOT FEASIBLE", (198, 40, 40))
            pdf.ln(8)
            _kv(pdf, "After-build value (ARV)", _money(verdict.arv))
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(
                0,
                4,
                _s(
                    "Estimated build cost exceeds achievable finished value; new construction is "
                    "not economical here at current pricing."
                ),
                align="L",
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        elif verdict.max_allowable_offer is not None:
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
                pdf.cell(23, 4.5, _s(severity.upper()), align="C", fill=True)
                pdf.cell(2, 4.5, "")
                pdf.set_text_color(*_INK)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.cell(
                    0, 4.5, _s(str(flag.get("label", ""))), new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
                pdf.set_x(41)
                pdf.set_text_color(*_MUTED)
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 4, _s(str(flag.get("detail", ""))), align="L")
        else:
            pdf.set_text_color(*_MUTED)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 5, "No major risk flags.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if report is not None:
        _section(pdf, "Investment report")
        confidence_color = _CONFIDENCE_COLOR.get(report.confidence, _MUTED)
        _tag(pdf, f"{report.confidence.upper()} CONFIDENCE", confidence_color)
        _tag(pdf, "AI-DRAFTED", _MUTED)
        pdf.ln(8)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 5, _s(report.headline), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
        for report_section in report.sections:
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(*_MUTED)
            heading = _s(report_section.heading.upper())
            pdf.cell(0, 4.5, heading, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(
                0, 4.5, _s(report_section.body), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
            )
            pdf.ln(1)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_BRAND)
        pdf.cell(0, 4.5, "RECOMMENDATION", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(
            0, 4.5, _s(report.recommendation), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

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
            pdf.cell(23, 4.5, _s(_STATUS_LABEL.get(item.status, "")), align="C", fill=True)
            pdf.cell(2, 4.5, "")
            pdf.set_text_color(*_INK)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.cell(0, 4.5, _s(item.category), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(34)
            pdf.set_text_color(*_MUTED)
            pdf.set_font("Helvetica", "", 8)
            pdf.multi_cell(0, 4, _s(item.detail), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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

    if verdict is not None and verdict.sources:
        _sources(pdf, verdict)

    pdf.ln(6)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        3.6,
        _s(f"Generated {stamp}. {disclaimer}"),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )

    return bytes(pdf.output())


def dossier_filename(parcel_number: str) -> str:
    return f"lotscope-dossier-{parcel_number.replace(':', '-')}.pdf"
