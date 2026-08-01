from dataclasses import dataclass
from datetime import date, datetime

from fpdf.enums import XPos, YPos

from lotscope.core.errors import MissingEconomicsError
from lotscope.reports.appeal_packet import _comp_table
from lotscope.reports.dossier import (
    _BRAND,
    _INK,
    _MUTED,
    _Dossier,
    _kv,
    _money,
    _s,
    _section,
)
from lotscope.valuation.schemas import ValuationResult

DEFAULT_EARNEST_MONEY = 1000.0
DEFAULT_CLOSE_DAYS = 30
DEFAULT_INSPECTION_DAYS = 10
DEFAULT_EXPIRATION_DAYS = 7

LOI_DISCLAIMER = (
    "This letter of intent is non-binding and provided for informational purposes only. It is "
    "not an offer capable of acceptance, a contract, or legal, tax, or financial advice. Any "
    "transaction is subject to a definitive written agreement, satisfactory due diligence, and "
    "independent professional review. Verify every figure independently before relying on it."
)


@dataclass(frozen=True)
class LoiTerms:
    all_cash: bool = True
    as_is: bool = True
    earnest_money: float = DEFAULT_EARNEST_MONEY
    close_days: int = DEFAULT_CLOSE_DAYS
    inspection_days: int = DEFAULT_INSPECTION_DAYS
    expiration: date | None = None


@dataclass(frozen=True)
class LoiSigner:
    entity_name: str | None = None
    signer_name: str | None = None
    signer_phone: str | None = None
    signer_email: str | None = None


@dataclass(frozen=True)
class LoiDocument:
    parcel_number: str
    local_key: str
    address: str
    offer_price: float
    price_provenance: str
    mao_framing: bool
    terms: LoiTerms
    signer: LoiSigner
    has_appendix: bool
    disclaimer: str
    generated_at: datetime


def compose_loi(
    *,
    parcel_number: str,
    local_key: str,
    address: str,
    max_allowable_offer: float | None,
    offer_price_override: float | None,
    terms: LoiTerms,
    signer: LoiSigner,
    has_comps: bool,
    generated_at: datetime,
) -> LoiDocument:
    if offer_price_override is not None:
        offer_price = offer_price_override
        if max_allowable_offer is not None:
            mao_framing = True
            price_provenance = (
                f"Offer reflects a user-entered price of {_money(offer_price)}, overriding the "
                f"LotScope Maximum Allowable Offer of {_money(max_allowable_offer)}."
            )
        else:
            mao_framing = False
            price_provenance = (
                f"Offer reflects a user-supplied price of {_money(offer_price)}. No LotScope "
                "valuation was available for this parcel."
            )
    elif max_allowable_offer is not None:
        offer_price = max_allowable_offer
        mao_framing = True
        price_provenance = (
            f"Offer price is the LotScope Maximum Allowable Offer of {_money(offer_price)} — the "
            "most payable while still meeting the target margin at this parcel's modeled value."
        )
    else:
        raise MissingEconomicsError(
            "No verdict economics are available for this parcel; compute the verdict first or "
            "supply a manual offer price."
        )

    return LoiDocument(
        parcel_number=parcel_number,
        local_key=local_key,
        address=address,
        offer_price=offer_price,
        price_provenance=price_provenance,
        mao_framing=mao_framing,
        terms=terms,
        signer=signer,
        has_appendix=has_comps,
        disclaimer=LOI_DISCLAIMER,
        generated_at=generated_at,
    )


def loi_filename(document: LoiDocument) -> str:
    return f"lotscope-loi-{document.parcel_number.replace(':', '-')}.pdf"


def _signature_line(pdf: _Dossier, label: str, x: float, width: float, y: float) -> None:
    pdf.set_draw_color(*_MUTED)
    pdf.line(x, y, x + width, y)
    pdf.set_xy(x, y + 1)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(width, 4, _s(label))


def _signature_block(pdf: _Dossier, document: LoiDocument) -> None:
    pdf.ln(6)
    _section(pdf, "Signatures")
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0,
        4,
        _s(
            "This letter is an expression of interest and does not create a binding obligation "
            "on either party. A binding agreement arises only on a fully executed purchase "
            "and sale agreement."
        ),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(8)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    column = (usable - 10) / 2
    y = pdf.get_y()
    buyer = document.signer.signer_name or document.signer.entity_name or "Buyer"
    _signature_line(pdf, _s(f"{buyer} - buyer"), pdf.l_margin, column, y)
    _signature_line(pdf, "Date", pdf.l_margin + column + 10, column, y)
    pdf.set_y(y + 14)
    y = pdf.get_y()
    _signature_line(pdf, "Owner - acknowledged", pdf.l_margin, column, y)
    _signature_line(pdf, "Date", pdf.l_margin + column + 10, column, y)
    pdf.set_y(y + 12)


def _terms_lines(terms: LoiTerms) -> list[tuple[str, str]]:
    return [
        ("Structure", "All cash" if terms.all_cash else "Financed"),
        ("Condition", "As-is, where-is" if terms.as_is else "Subject to inspection remedies"),
        ("Earnest money deposit", _money(terms.earnest_money)),
        ("Inspection / due-diligence period", f"{terms.inspection_days} days"),
        ("Target closing", f"{terms.close_days} days from acceptance"),
        (
            "Offer valid through",
            terms.expiration.strftime("%B %-d, %Y")
            if terms.expiration is not None
            else "Open until withdrawn in writing",
        ),
    ]


def render_loi_pdf(document: LoiDocument, valuation: ValuationResult | None) -> bytes:
    pdf = _Dossier(format="A4")
    pdf.running_title = _s(document.address)
    pdf.running_subtitle = _s(f"Parcel {document.parcel_number}")
    pdf.footer_note = _s("Letter of intent - non-binding")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(16, 16, 16)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_fill_color(*_BRAND)
    pdf.rect(0, 0, pdf.w, 26, style="F")
    pdf.set_xy(16, 7)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(210, 225, 245)
    pdf.cell(0, 4, "LOTSCOPE PHL - LETTER OF INTENT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, _s(document.address))
    pdf.set_y(30)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(
        0,
        5,
        _s(f"Parcel {document.parcel_number} (OPA {document.local_key})"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(
        0,
        5,
        _s(
            "The undersigned submits this non-binding letter of intent to purchase the property "
            "identified above on the following principal terms."
        ),
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(3)

    _section(pdf, "Offer")
    _kv(pdf, "Purchase price", _money(document.offer_price))
    pdf.ln(1)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(
        0, 4.2, _s(document.price_provenance), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.ln(2)

    _section(pdf, "Principal terms")
    for label, value in _terms_lines(document.terms):
        _kv(pdf, label, value)

    if document.has_appendix and valuation is not None and valuation.comps:
        pdf.ln(2)
        _section(pdf, "Comparable-sales evidence")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_MUTED)
        intro = (
            f"{valuation.comp_count} recorded arm's-length sale(s) support the offer price."
            if document.mao_framing
            else f"{valuation.comp_count} recorded arm's-length sale(s) in the area, for reference."
        )
        pdf.cell(0, 5, _s(intro), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(1)
        _comp_table(pdf, valuation)
        for reason in valuation.reasons:
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_MUTED)
            pdf.multi_cell(0, 4, _s(reason), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4)
    _section(pdf, "Submitted by")
    _kv(pdf, "Entity", document.signer.entity_name or "-")
    _kv(pdf, "Signer", document.signer.signer_name or "-")
    _kv(pdf, "Phone", document.signer.signer_phone or "-")
    _kv(pdf, "Email", document.signer.signer_email or "-")

    _signature_block(pdf, document)

    pdf.ln(6)
    pdf.set_draw_color(*_MUTED)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 3.8, _s(f"Prepared {document.generated_at.strftime('%B %-d, %Y')}."))
    pdf.ln(1)
    pdf.multi_cell(0, 3.8, _s(document.disclaimer), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
