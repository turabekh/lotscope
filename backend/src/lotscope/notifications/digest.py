from dataclasses import dataclass
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
