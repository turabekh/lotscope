from dataclasses import dataclass
from datetime import date, datetime

from fpdf.enums import XPos, YPos

from lotscope.buyers.derivation import RepeatBuyer
from lotscope.packet.schemas import PacketLot
from lotscope.reports.dossier import (
    _BRAND,
    _INK,
    _LINE,
    _MUTED,
    _Dossier,
    _kv,
    _money,
    _note,
    _s,
    _section,
)
from lotscope.reports.letter_copy import LETTER_COPY

LETTER_PURCHASES = 3

_VERDICT_COLOR = {"BID": (21, 128, 61), "LOOK": (180, 128, 9), "PASS": (127, 29, 29)}


@dataclass(frozen=True)
class LetterPurchase:
    parcel_number: str
    address: str | None
    sale_date: date
    sale_price: float
    lot: PacketLot | None


@dataclass(frozen=True)
class LetterContext:
    buyer: RepeatBuyer
    purchases: list[LetterPurchase]
    window_months: int
    register_url: str
    invite_url: str | None
    invite_code: str | None
    generated_at: datetime
    sources: list[tuple[str, str]]


def _footnote(pdf: _Dossier, text: str) -> None:
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 3.2, _s(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)


def _paragraph(pdf: _Dossier, text: str, size: float = 9.5) -> None:
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 4.6, _s(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


def _purchase_block(pdf: _Dossier, purchase: LetterPurchase) -> None:
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*_INK)
    title = purchase.address or purchase.parcel_number
    pdf.cell(0, 5.5, _s(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        4.5,
        _s(
            f"{purchase.parcel_number} - bought {purchase.sale_date.isoformat()} for "
            f"{_money(purchase.sale_price)}"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    _footnote(pdf, "Source: rtt_summary (recorded deed) - opendataphilly.org")

    lot = purchase.lot
    if lot is None:
        _note(pdf, LETTER_COPY["unavailable"])
        pdf.ln(2)
        return

    by_right = (
        "unknown"
        if lot.can_build_by_right is None
        else ("yes" if lot.can_build_by_right else "no, a variance is needed")
    )
    _kv(pdf, "Buildable by right", by_right)
    if lot.by_right_units is not None:
        _kv(pdf, "By-right units", str(lot.by_right_units))
    if lot.dimensional_reason:
        _note(pdf, lot.dimensional_reason)
    if lot.provision_id:
        _footnote(pdf, f"Title 14 provision {lot.provision_id} - source: zoning_base_districts")
    _kv(pdf, "Maximum allowable offer", _money(lot.max_allowable_offer))
    _footnote(
        pdf,
        "At platform default assumptions, not yours - source: LotScope deal engine, "
        "computed today from current zoning, comps and assessment data",
    )

    if lot.red_flags:
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 4.5, _s("Open red flags today"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for flag in lot.red_flags:
            pdf.set_font("Helvetica", "", 8.5)
            pdf.multi_cell(
                0,
                4,
                _s(f"- {flag.label}: {flag.detail}"),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            _footnote(pdf, f"  {flag.source} - {flag.source_url}")
    else:
        _note(pdf, "Nothing we hold flags this lot today.")
    pdf.ln(2)


def render_buyer_letter(context: LetterContext) -> bytes:
    pdf = _Dossier(orientation="P", unit="mm", format="A4")
    pdf.running_title = "LotScope PHL"
    pdf.running_subtitle = context.buyer.display_name
    pdf.footer_note = (
        "LotScope is an information service, not a broker, lender or law firm. "
        "Figures are computed from public records and are not an appraisal."
    )
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*_BRAND)
    pdf.cell(0, 8, _s(LETTER_COPY["heading"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        5,
        _s(f"Prepared for {context.buyer.display_name} on {context.generated_at:%-d %B %Y}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)

    _paragraph(
        pdf,
        LETTER_COPY["intro"].format(
            purchase_count=context.buyer.purchase_count,
            window_months=context.window_months,
        ),
    )
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)

    if not context.purchases:
        _note(pdf, LETTER_COPY["no_purchases"])
    for purchase in context.purchases[:LETTER_PURCHASES]:
        _purchase_block(pdf, purchase)

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*_BRAND)
    pdf.cell(0, 7, _s(LETTER_COPY["offer_heading"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)
    _paragraph(pdf, LETTER_COPY["offer_body"])

    if context.invite_url:
        _paragraph(pdf, LETTER_COPY["link_intro"])
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_BRAND)
        pdf.multi_cell(0, 4.6, _s(context.invite_url), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)
    elif context.invite_code:
        _paragraph(pdf, LETTER_COPY["code_intro"].format(register_url=context.register_url))
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(*_BRAND)
        pdf.cell(0, 12, _s(context.invite_code), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*_INK)

    pdf.ln(2)
    _paragraph(pdf, LETTER_COPY["closing"], size=8.5)

    _section(pdf, LETTER_COPY["sources_heading"])
    for label, url in context.sources:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 4.2, _s(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _footnote(pdf, url)

    return bytes(pdf.output())


def letter_filename(buyer_key: str) -> str:
    slug = "".join(char if char.isalnum() else "-" for char in buyer_key.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"lotscope-letter-{slug}.pdf"
