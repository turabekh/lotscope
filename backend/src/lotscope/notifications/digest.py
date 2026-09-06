from dataclasses import dataclass
from datetime import date
from html import escape

_SEVERITY_COLOR = {"high": "#c62828", "medium": "#ef6c00", "info": "#0277bd"}


@dataclass(frozen=True)
class DigestChange:
    label: str
    severity: str


@dataclass(frozen=True)
class DigestParcel:
    parcel_number: str
    address: str | None
    changes: list[DigestChange]


@dataclass(frozen=True)
class DigestContent:
    parcels: list[DigestParcel]

    @property
    def total_changes(self) -> int:
        return sum(len(parcel.changes) for parcel in self.parcels)


def digest_subject(content: DigestContent) -> str:
    lots = len(content.parcels)
    updates = content.total_changes
    u = "" if updates == 1 else "s"
    p = "" if lots == 1 else "s"
    return f"{updates} update{u} on {lots} watched lot{p}"


def render_digest_text(
    content: DigestContent, *, watchlist_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = ["Updates on your watched Philadelphia lots:", ""]
    for parcel in content.parcels:
        lines.append(parcel.address or parcel.parcel_number)
        for change in parcel.changes:
            lines.append(f"  - {change.label}")
        lines.append("")
    lines.append(f"View your watchlist: {watchlist_url}")
    lines.append("")
    lines.append("This is an informational alert, not legal or financial advice.")
    lines.append(f"Unsubscribe: {unsubscribe_url}")
    lines.append(postal_address)
    return "\n".join(lines)


def render_digest_html(
    content: DigestContent, *, watchlist_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    blocks: list[str] = []
    for parcel in content.parcels:
        title = escape(parcel.address or parcel.parcel_number)
        chips = "".join(
            f'<span style="display:inline-block;margin:2px 4px 2px 0;padding:2px 8px;'
            f"border-radius:10px;font-size:12px;color:#fff;"
            f'background:{_SEVERITY_COLOR.get(change.severity, "#607d8b")};">'
            f"{escape(change.label)}</span>"
            for change in parcel.changes
        )
        blocks.append(
            f'<div style="padding:12px 0;border-bottom:1px solid #eceff1;">'
            f'<div style="font-weight:600;font-size:15px;color:#1f2933;">{title}</div>'
            f'<div style="margin-top:4px;">{chips}</div></div>'
        )
    body = "".join(blocks)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        '<div style="font-size:13px;opacity:0.85;">Updates on your watched lots</div></div>'
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{body}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(watchlist_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "View your watchlist</a></div>"
        '<div style="margin-top:18px;font-size:11px;color:#90a4ae;line-height:1.5;">'
        "Informational only — not legal, financial, or real-estate advice. "
        f'You receive this because you saved lots on LotScope. <a href="{escape(unsubscribe_url)}" '
        'style="color:#90a4ae;">Unsubscribe</a>.<br>'
        f"{escape(postal_address)}</div></div></div>"
    )


@dataclass(frozen=True)
class DealReminderItem:
    address: str
    stage: str
    next_action: str | None
    due_label: str
    overdue: bool


@dataclass(frozen=True)
class DealReminderContent:
    items: list[DealReminderItem]

    @property
    def overdue_count(self) -> int:
        return sum(1 for item in self.items if item.overdue)


def deal_reminder_subject(content: DealReminderContent) -> str:
    total = len(content.items)
    overdue = content.overdue_count
    deals = "deal" if total == 1 else "deals"
    if overdue:
        return f"{total} {deals} need action ({overdue} overdue)"
    return f"{total} {deals} due today"


def render_deal_reminder_text(
    content: DealReminderContent, *, pipeline_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = ["Deals that need action:", ""]
    for item in content.items:
        lines.append(f"{item.address} [{item.stage}] — {item.due_label}")
        if item.next_action:
            lines.append(f"  Next: {item.next_action}")
    lines.append("")
    lines.append(f"Open your pipeline: {pipeline_url}")
    lines.append("")
    lines.append("Informational only — not legal, financial, or real-estate advice.")
    lines.append(f"Unsubscribe: {unsubscribe_url}")
    lines.append(postal_address)
    return "\n".join(lines)


def render_deal_reminder_html(
    content: DealReminderContent, *, pipeline_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    rows: list[str] = []
    for item in content.items:
        due_color = "#c62828" if item.overdue else "#ef6c00"
        action = (
            f'<div style="color:#546e7a;font-size:13px;">{escape(item.next_action)}</div>'
            if item.next_action
            else ""
        )
        rows.append(
            f'<div style="padding:10px 0;border-bottom:1px solid #eceff1;">'
            f'<div style="font-weight:600;font-size:15px;color:#1f2933;">{escape(item.address)}'
            f'</div><div style="font-size:13px;color:#607d8b;">{escape(item.stage)} · '
            f'<span style="color:{due_color};font-weight:600;">{escape(item.due_label)}</span>'
            f"</div>{action}</div>"
        )
    body = "".join(rows)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        '<div style="font-size:13px;opacity:0.85;">Deals that need action</div></div>'
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{body}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(pipeline_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Open your pipeline</a></div>"
        '<div style="margin-top:18px;font-size:11px;color:#90a4ae;line-height:1.5;">'
        "Informational only — not legal, financial, or real-estate advice. "
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a>.<br>'
        f"{escape(postal_address)}</div></div></div>"
    )


@dataclass(frozen=True)
class SalesWeekItem:
    address: str
    sale_date: str
    days_until: int
    opening_bid: float | None
    opportunity_score: int | None


@dataclass(frozen=True)
class SalesWeekContent:
    label: str
    items: list[SalesWeekItem]


def sales_week_subject(content: SalesWeekContent) -> str:
    return f"{len(content.items)} {content.label.lower()} this week"


def _sales_week_line(item: SalesWeekItem) -> str:
    when = "today" if item.days_until == 0 else f"in {item.days_until} days"
    bid = f" · opening ${round(item.opening_bid):,}" if item.opening_bid is not None else ""
    return f"{item.address} — {item.sale_date} ({when}){bid}"


def render_sales_week_text(
    content: SalesWeekContent, *, calendar_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = [f"{content.label} in the next 7 days:", ""]
    for item in content.items:
        lines.append(f"  - {_sales_week_line(item)}")
    lines.append("")
    lines.append(f"Open the sales calendar: {calendar_url}")
    lines.append("")
    lines.append("Informational only — not legal, financial, or real-estate advice.")
    lines.append(f"Unsubscribe: {unsubscribe_url}")
    lines.append(postal_address)
    return "\n".join(lines)


def render_sales_week_html(
    content: SalesWeekContent, *, calendar_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    rows = "".join(
        f'<div style="padding:8px 0;border-bottom:1px solid #eceff1;font-size:14px;color:#1f2933;">'
        f"<b>{escape(item.address)}</b><br>"
        f'<span style="color:#607d8b;font-size:13px;">{escape(item.sale_date)} · '
        f"{'today' if item.days_until == 0 else f'in {item.days_until} days'}"
        f"{f' · opening ${round(item.opening_bid):,}' if item.opening_bid is not None else ''}"
        "</span></div>"
        for item in content.items
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        f'<div style="font-size:13px;opacity:0.85;">{escape(content.label)} this week</div></div>'
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{rows}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(calendar_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Open the sales calendar</a></div>"
        '<div style="margin-top:18px;font-size:11px;color:#90a4ae;line-height:1.5;">'
        "Informational only — not legal, financial, or real-estate advice. "
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a>.<br>'
        f"{escape(postal_address)}</div></div></div>"
    )


@dataclass(frozen=True)
class PacketLotLine:
    address: str
    grade: str
    opening_bid: str
    offer: str


@dataclass(frozen=True)
class PacketEmailContent:
    sale_date: date
    target_use: str
    vacant: int
    passing: int
    items: list[PacketLotLine]


PACKET_EMAIL_ROWS = 5


def packet_email_subject(content: PacketEmailContent) -> str:
    lots = "lot" if content.passing == 1 else "lots"
    return (
        f"Sale Packet {content.sale_date.isoformat()} — "
        f"{content.passing} {lots} worth a look of {content.vacant} vacant"
    )


def render_packet_email_text(
    content: PacketEmailContent, *, packets_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = [
        f"Sheriff sale {content.sale_date.isoformat()}, graded as {content.target_use}.",
        f"{content.passing} of {content.vacant} vacant lots are worth your time.",
        "",
    ]
    if content.items:
        lines.append("Top lots:")
        for item in content.items:
            lines.append(
                f"  {item.address} [{item.grade}] — opening {item.opening_bid}, {item.offer}"
            )
    else:
        lines.append("No lot on this date passed your buy box. The packet says why for each.")
    lines += [
        "",
        "The full packet is attached as a PDF.",
        f"Your packets: {packets_url}",
        "",
        "The published opening bid is a minimum and is nominal on tax sales.",
        "Informational only — not legal, financial, or real-estate advice.",
        f"Unsubscribe: {unsubscribe_url}",
        postal_address,
    ]
    return "\n".join(lines)


def render_packet_email_html(
    content: PacketEmailContent, *, packets_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    if content.items:
        rows = "".join(
            f'<tr><td style="padding:6px 8px;border-bottom:1px solid #eceff1;">'
            f"{escape(item.address)}</td>"
            f'<td style="padding:6px 8px;border-bottom:1px solid #eceff1;font-weight:600;">'
            f"{escape(item.grade)}</td>"
            f'<td style="padding:6px 8px;border-bottom:1px solid #eceff1;">'
            f"{escape(item.opening_bid)}</td>"
            f'<td style="padding:6px 8px;border-bottom:1px solid #eceff1;">'
            f"{escape(item.offer)}</td></tr>"
            for item in content.items
        )
        table = (
            '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
            '<tr style="text-align:left;color:#607d8b;">'
            '<th style="padding:6px 8px;">Address</th><th style="padding:6px 8px;">Grade</th>'
            '<th style="padding:6px 8px;">Opening</th><th style="padding:6px 8px;">Offer</th></tr>'
            f"{rows}</table>"
        )
    else:
        table = (
            '<div style="font-size:14px;color:#546e7a;">No lot on this date passed your buy '
            "box. The packet says why for each.</div>"
        )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:620px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        f'<div style="font-size:13px;opacity:0.85;">Sheriff sale '
        f"{escape(content.sale_date.isoformat())} · graded as "
        f"{escape(content.target_use)}</div></div>"
        '<div style="padding:12px 20px 16px;border:1px solid #eceff1;border-top:none;">'
        f'<div style="font-size:14px;margin-bottom:10px;">{content.passing} of {content.vacant} '
        f"vacant lots are worth your time.</div>{table}"
        f'<div style="margin-top:16px;text-align:center;">'
        f'<a href="{escape(packets_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Open your packets</a></div>"
        '<div style="margin-top:14px;font-size:11px;color:#78909c;">The published opening bid is '
        "a minimum and is nominal on tax sales. Informational only — not legal, financial, or "
        "real-estate advice.</div>"
        f'<div style="margin-top:6px;font-size:11px;color:#90a4ae;">'
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a> · '
        f"{escape(postal_address)}</div></div></div>"
    )


@dataclass(frozen=True)
class SaleChangeLine:
    address: str
    change: str


@dataclass(frozen=True)
class SaleChangeContent:
    sale_date: date
    items: list[SaleChangeLine]


def sale_change_subject(content: SaleChangeContent) -> str:
    count = len(content.items)
    changes = "change" if count == 1 else "changes"
    return f"{count} {changes} to the {content.sale_date.isoformat()} sheriff sale"


def render_sale_change_text(
    content: SaleChangeContent, *, packets_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = [f"Changes on lots in your {content.sale_date.isoformat()} packet:", ""]
    for item in content.items:
        lines.append(f"  {item.address} — {item.change}")
    lines += [
        "",
        f"Your packets: {packets_url}",
        "",
        "Informational only — not legal, financial, or real-estate advice.",
        f"Unsubscribe: {unsubscribe_url}",
        postal_address,
    ]
    return "\n".join(lines)


def render_sale_change_html(
    content: SaleChangeContent, *, packets_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    rows = "".join(
        f'<div style="padding:8px 0;border-bottom:1px solid #eceff1;">'
        f'<span style="font-weight:600;">{escape(item.address)}</span> — '
        f"{escape(item.change)}</div>"
        for item in content.items
    )
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        f'<div style="font-size:13px;opacity:0.85;">Changes to the '
        f"{escape(content.sale_date.isoformat())} sale</div></div>"
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{rows}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(packets_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Open your packets</a></div>"
        '<div style="margin-top:14px;font-size:11px;color:#78909c;">Informational only — not '
        "legal, financial, or real-estate advice.</div>"
        f'<div style="margin-top:6px;font-size:11px;color:#90a4ae;">'
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a> · '
        f"{escape(postal_address)}</div></div></div>"
    )


@dataclass(frozen=True)
class BriefContent:
    brief_date: date
    body: str
    signal_count: int
    analyst_url: str


def brief_subject(content: BriefContent) -> str:
    return f"LotScope brief — {content.brief_date.strftime('%a %-d %b')}"


def render_brief_text(content: BriefContent, unsubscribe_url: str) -> str:
    return (
        f"{content.body.strip()}\n\n"
        f"{content.signal_count} change{'' if content.signal_count == 1 else 's'} "
        f"overnight. Open the analyst: {content.analyst_url}\n\n"
        f"Stop these emails: {unsubscribe_url}\n"
    )


def render_brief_html(content: BriefContent, unsubscribe_url: str) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 10px">{escape(line)}</p>'
        for line in content.body.strip().splitlines()
        if line.strip()
    )
    return (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:14px;'
        'line-height:1.5;color:#1a1a1a">'
        f'<h2 style="margin:0 0 12px;font-size:16px">{escape(brief_subject(content))}</h2>'
        f"{paragraphs}"
        f'<p style="margin:16px 0 0"><a href="{escape(content.analyst_url)}">'
        "Open the analyst</a></p>"
        f'<p style="margin:12px 0 0;color:#666;font-size:12px">'
        f'<a href="{escape(unsubscribe_url)}">Stop these emails</a></p>'
        "</div>"
    )
