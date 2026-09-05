from fpdf.enums import XPos, YPos

from lotscope.packet.schemas import PacketLot, PacketModel
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
    _tag,
)

_VERDICT_COLOR = {
    "BID": (21, 128, 61),
    "LOOK": (180, 128, 9),
    "PASS": (127, 29, 29),
}

_SUMMARY_COLUMNS: tuple[tuple[str, float], ...] = (
    ("Verdict", 18),
    ("Address", 62),
    ("Parcel", 26),
    ("Case", 24),
    ("Zoning", 20),
    ("Lot sqft", 20),
    ("Opening", 24),
    ("MAO", 26),
    ("Margin", 18),
    ("Flags", 14),
)


def _percent(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "-"


def _footnote(pdf: _Dossier, text: str) -> None:
    pdf.set_font("Helvetica", "", 6.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 3.2, _s(text), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_INK)


def _header_block(pdf: _Dossier, packet: PacketModel) -> None:
    header = packet.header
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_BRAND)
    pdf.cell(
        0,
        8,
        _s(f"Sale Packet - {header.sale_date.isoformat()}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    types = ", ".join(header.sale_types) if header.sale_types else "not stated"
    pdf.cell(
        0,
        5,
        _s(
            f"{header.listings} listings - {header.vacant} vacant - "
            f"{header.passing_buy_box} pass your buy box - sale types: {types}"
        ),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.cell(
        0,
        5,
        _s(f"Generated {header.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    pdf.ln(2)

    _section(pdf, "Data as of")
    for entry in header.data_as_of:
        fetched = entry.fetched_at.strftime("%Y-%m-%d") if entry.fetched_at else "unknown"
        vintage = f", vintage {entry.data_vintage.isoformat()}" if entry.data_vintage else ""
        _kv(pdf, entry.source, f"fetched {fetched}{vintage}")
        _footnote(pdf, entry.source_url)


def _summary_table(pdf: _Dossier, packet: PacketModel) -> None:
    _section(pdf, "Every lot screened")
    pdf.set_font("Helvetica", "B", 7.5)
    pdf.set_text_color(*_MUTED)
    for label, width in _SUMMARY_COLUMNS:
        pdf.cell(width, 5, _s(label))
    pdf.ln(5)
    pdf.set_draw_color(*_LINE)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(1)

    rows: list[tuple[str, PacketLot | None, str, str]] = [
        (kept.verdict, kept, "", "") for kept in packet.lots
    ]
    rows.extend(("PASS", None, entry.address or "", entry.parcel_number) for entry in packet.passed)

    pdf.set_font("Helvetica", "", 7.5)
    for verdict, row, address, parcel in rows:
        if pdf.get_y() > pdf.h - 25:
            pdf.add_page()
        pdf.set_text_color(*_VERDICT_COLOR[verdict])
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.cell(_SUMMARY_COLUMNS[0][1], 5, _s(verdict))
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(*_INK)
        if row is None:
            pdf.cell(_SUMMARY_COLUMNS[1][1], 5, _s(address[:38]))
            pdf.cell(_SUMMARY_COLUMNS[2][1], 5, _s(parcel))
            pdf.ln(5)
            continue
        pdf.cell(_SUMMARY_COLUMNS[1][1], 5, _s((row.address or "")[:38]))
        pdf.cell(_SUMMARY_COLUMNS[2][1], 5, _s(row.parcel_number))
        pdf.cell(_SUMMARY_COLUMNS[3][1], 5, _s(row.case_number or "-"))
        pdf.cell(_SUMMARY_COLUMNS[4][1], 5, _s(row.zoning_code or "-"))
        pdf.cell(
            _SUMMARY_COLUMNS[5][1],
            5,
            _s(f"{row.lot_area_sqft:,.0f}" if row.lot_area_sqft is not None else "-"),
        )
        pdf.cell(_SUMMARY_COLUMNS[6][1], 5, _s(_money(row.opening_bid)))
        pdf.cell(_SUMMARY_COLUMNS[7][1], 5, _s(_money(row.max_allowable_offer)))
        pdf.cell(_SUMMARY_COLUMNS[8][1], 5, _s(_percent(row.est_margin)))
        pdf.cell(_SUMMARY_COLUMNS[9][1], 5, _s(str(len(row.red_flags))))
        pdf.ln(5)


def _lot_page(pdf: _Dossier, lot: PacketLot) -> None:
    pdf.add_page(orientation="P")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*_BRAND)
    pdf.cell(0, 8, _s(lot.address or lot.parcel_number), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    _tag(pdf, lot.verdict, _VERDICT_COLOR[lot.verdict])
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 4.5, _s(lot.verdict_reason), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    _section(pdf, "The listing")
    _kv(pdf, "Parcel", lot.parcel_number)
    _kv(pdf, "Case", lot.case_number or "not stated")
    _kv(pdf, "Sale type", lot.sale_type or "not stated")
    _kv(
        pdf,
        "Status",
        f"{lot.status or 'not stated'}"
        f"{' - scheduled for auction' if lot.is_scheduled else ' - not scheduled'}",
    )
    _kv(pdf, "Opening bid", _money(lot.opening_bid))
    _kv(pdf, "Plaintiff", lot.plaintiff or "not stated")

    _section(pdf, "The lot")
    _kv(
        pdf,
        "Lot area",
        f"{lot.lot_area_sqft:,.0f} sqft" if lot.lot_area_sqft is not None else "not recorded",
    )
    _kv(pdf, "Zoning", lot.zoning_code or "not recorded")
    _kv(pdf, "Overlays", ", ".join(lot.overlays) if lot.overlays else "none recorded")
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
        _footnote(pdf, f"Title 14 provision {lot.provision_id}")

    _section(pdf, "The offer")
    _kv(pdf, "Maximum allowable offer", _money(lot.max_allowable_offer))
    _kv(pdf, "Estimated margin", _percent(lot.est_margin))
    for item in lot.sensitive_inputs:
        _note(pdf, f"{item.name}: {item.detail}")

    _section(pdf, "Red flags")
    if not lot.red_flags:
        _note(pdf, "Nothing we hold flags this lot. That is not the same as nothing being wrong.")
    for flag in lot.red_flags:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*_INK)
        pdf.cell(0, 5, _s(f"{flag.label} ({flag.severity})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(0, 4, _s(flag.detail), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        _footnote(pdf, f"{flag.source} - {flag.source_url}")

    _section(pdf, "Comparable sales")
    if not lot.comps:
        _note(pdf, "No recorded sale nearby was close enough to price this lot.")
    for comp in lot.comps:
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_INK)
        sold = comp.sale_date.isoformat() if comp.sale_date else "date not recorded"
        pdf.multi_cell(
            0,
            4,
            _s(f"{comp.address or comp.parcel_number} - {_money(comp.sale_price)} - {sold}"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        _note(pdf, comp.reason)
        _footnote(pdf, f"{comp.source} - {comp.source_url}")
    if lot.comp_range_low is not None and lot.comp_range_high is not None:
        _kv(pdf, "Comp range", f"{_money(lot.comp_range_low)} - {_money(lot.comp_range_high)}")

    _section(pdf, "Verify before bidding")
    for caveat in lot.verify_before_bidding:
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*_INK)
        pdf.multi_cell(0, 4, _s(f"- {caveat}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _pass_appendix(pdf: _Dossier, packet: PacketModel) -> None:
    if not packet.passed and not packet.non_vacant_appendix:
        return
    pdf.add_page(orientation="P")
    _section(pdf, "Passed lots, and why")
    for entry in packet.passed:
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*_INK)
        pdf.cell(
            0,
            4.5,
            _s(f"{entry.address or entry.parcel_number} ({entry.parcel_number})"),
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        _note(pdf, entry.reason)

    if packet.non_vacant_appendix:
        _section(pdf, "Not vacant, so not screened")
        for entry in packet.non_vacant_appendix:
            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(*_INK)
            pdf.multi_cell(
                0,
                4,
                _s(f"{entry.address or entry.parcel_number} ({entry.parcel_number})"),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )


def render_packet_pdf(packet: PacketModel) -> bytes:
    pdf = _Dossier(orientation="L", unit="mm", format="A4")
    pdf.running_title = f"Sale Packet {packet.header.sale_date.isoformat()}"
    pdf.running_subtitle = (
        f"{packet.header.passing_buy_box} of {packet.header.vacant} vacant lots pass"
    )
    pdf.footer_note = (
        "LotScope screens public records and is not legal, title or financial advice. "
        "Verify every figure before bidding."
    )
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.alias_nb_pages()
    pdf.add_page()

    _header_block(pdf, packet)
    _summary_table(pdf, packet)

    for lot in packet.lots:
        _lot_page(pdf, lot)

    _pass_appendix(pdf, packet)
    return bytes(pdf.output())


def packet_filename(sale_date: str, user_id: int) -> str:
    return f"lotscope-sale-packet-{sale_date}-u{user_id}.pdf"
