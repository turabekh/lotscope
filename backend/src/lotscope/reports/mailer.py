from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from lotscope.reports.dossier import _INK, _MUTED, _s

_BODY_SIZE = 11
_LINE_HEIGHT = 6.0


@dataclass(frozen=True)
class Letter:
    owner: str
    mailing_address: str
    body: str


class _Mailer(FPDF):
    def footer(self) -> None:
        self.set_y(-16)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*_MUTED)
        self.multi_cell(0, 3.4, _s(self._disclaimer))

    def _bind(self, disclaimer: str) -> None:
        self._disclaimer = disclaimer


def _address_block(pdf: _Mailer, lines: list[str]) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_INK)
    for line in lines:
        pdf.cell(0, 5, _s(line), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def render_letters_pdf(
    *,
    sender_name: str,
    sender_contact: str,
    letters: list[Letter],
    generated_at: datetime,
    disclaimer: str,
) -> bytes:
    pdf = _Mailer(format="Letter")
    pdf._bind(disclaimer)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(20, 20, 20)
    stamp = generated_at.strftime("%B %-d, %Y")

    for letter in letters:
        pdf.add_page()
        _address_block(pdf, [sender_name, *sender_contact.splitlines()])
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*_MUTED)
        pdf.cell(0, 5, _s(stamp), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(4)
        _address_block(pdf, [letter.owner, *letter.mailing_address.splitlines()])
        pdf.ln(8)
        pdf.set_font("Helvetica", "", _BODY_SIZE)
        pdf.set_text_color(*_INK)
        for paragraph in letter.body.split("\n\n"):
            pdf.multi_cell(0, _LINE_HEIGHT, _s(paragraph))
            pdf.ln(3)
        pdf.ln(4)
        pdf.set_font("Helvetica", "", _BODY_SIZE)
        pdf.cell(0, _LINE_HEIGHT, _s("Sincerely,"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(6)
        pdf.cell(0, _LINE_HEIGHT, _s(sender_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())


def letters_filename() -> str:
    return "lotscope-outreach-letters.pdf"
