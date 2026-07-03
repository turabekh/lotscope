from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class MatchAlertParcel:
    parcel_number: str
    address: str | None
    opportunity_score: int | None


@dataclass(frozen=True)
class MatchAlertSearch:
    name: str
    parcels: list[MatchAlertParcel] = field(default_factory=list)


@dataclass(frozen=True)
class MatchAlertContent:
    searches: list[MatchAlertSearch]

    @property
    def total_matches(self) -> int:
        return sum(len(search.parcels) for search in self.searches)


def match_alert_subject(content: MatchAlertContent) -> str:
    lots = content.total_matches
    searches = len(content.searches)
    lot = "" if lots == 1 else "s"
    if searches == 1:
        return f"{lots} new lot{lot} match “{content.searches[0].name}”"
    return f"{lots} new lot{lot} match {searches} of your saved searches"


def render_match_alert_text(
    content: MatchAlertContent, *, searches_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = ["New Philadelphia lots match your saved searches:", ""]
    for search in content.searches:
        lines.append(f"{search.name} ({len(search.parcels)} new)")
        for parcel in search.parcels:
            label = parcel.address or parcel.parcel_number
            score = f" — opportunity {parcel.opportunity_score}" if parcel.opportunity_score else ""
            lines.append(f"  - {label}{score}")
        lines.append("")
    lines.append(f"Review your saved searches: {searches_url}")
    lines.append("")
    lines.append("This is an informational alert, not legal or financial advice.")
    lines.append(f"Unsubscribe: {unsubscribe_url}")
    lines.append(postal_address)
    return "\n".join(lines)


def render_match_alert_html(
    content: MatchAlertContent, *, searches_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    blocks: list[str] = []
    for search in content.searches:
        rows = "".join(
            f'<div style="padding:4px 0;color:#1f2933;font-size:14px;">'
            f"{escape(parcel.address or parcel.parcel_number)}"
            + (
                f'<span style="color:#607d8b;font-size:12px;"> — opportunity '
                f"{parcel.opportunity_score}</span>"
                if parcel.opportunity_score
                else ""
            )
            + "</div>"
            for parcel in search.parcels
        )
        blocks.append(
            f'<div style="padding:12px 0;border-bottom:1px solid #eceff1;">'
            f'<div style="font-weight:600;font-size:15px;color:#1f2933;">'
            f"{escape(search.name)} "
            f'<span style="color:#1565c0;">({len(search.parcels)} new)</span></div>'
            f'<div style="margin-top:4px;">{rows}</div></div>'
        )
    body = "".join(blocks)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        '<div style="font-size:13px;opacity:0.85;">New lots match your saved searches</div></div>'
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{body}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(searches_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Review saved searches</a></div>"
        '<div style="margin-top:18px;font-size:11px;color:#90a4ae;line-height:1.5;">'
        "Informational only — not legal, financial, or real-estate advice. "
        f"You receive this because you saved searches on LotScope. "
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a>.<br>'
        f"{escape(postal_address)}</div></div></div>"
    )


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
class FeedDigestLine:
    label: str
    count: int


@dataclass(frozen=True)
class FeedDigestSearch:
    name: str
    total: int
    lines: list[FeedDigestLine] = field(default_factory=list)


@dataclass(frozen=True)
class FeedDigestContent:
    searches: list[FeedDigestSearch]

    @property
    def total_events(self) -> int:
        return sum(search.total for search in self.searches)


def feed_digest_subject(content: FeedDigestContent) -> str:
    total = content.total_events
    change = "change" if total == 1 else "changes"
    return f"{total} {change} in your buy box today"


def render_feed_digest_text(
    content: FeedDigestContent, *, feed_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    lines = ["Since yesterday in your buy box:", ""]
    for search in content.searches:
        lines.append(f"{search.name} ({search.total})")
        for line in search.lines:
            lines.append(f"  - {line.count} {line.label}")
        lines.append("")
    lines.append(f"Open your deal feed: {feed_url}")
    lines.append("")
    lines.append("Informational only — not legal, financial, or real-estate advice.")
    lines.append(f"Unsubscribe: {unsubscribe_url}")
    lines.append(postal_address)
    return "\n".join(lines)


def render_feed_digest_html(
    content: FeedDigestContent, *, feed_url: str, unsubscribe_url: str, postal_address: str
) -> str:
    blocks: list[str] = []
    for search in content.searches:
        rows = "".join(
            f'<div style="padding:3px 0;color:#1f2933;font-size:14px;">'
            f'<b>{line.count}</b> {escape(line.label)}</div>'
            for line in search.lines
        )
        blocks.append(
            f'<div style="padding:12px 0;border-bottom:1px solid #eceff1;">'
            f'<div style="font-weight:600;font-size:15px;color:#1f2933;">'
            f"{escape(search.name)} "
            f'<span style="color:#1565c0;">({search.total})</span></div>'
            f'<div style="margin-top:4px;">{rows}</div></div>'
        )
    body = "".join(blocks)
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;'
        'color:#1f2933;">'
        '<div style="background:#0f4ba8;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">'
        '<div style="font-size:18px;font-weight:700;">LotScope PHL</div>'
        '<div style="font-size:13px;opacity:0.85;">Since yesterday in your buy box</div></div>'
        f'<div style="padding:8px 20px 16px;border:1px solid #eceff1;border-top:none;">{body}'
        f'<div style="margin-top:18px;text-align:center;">'
        f'<a href="{escape(feed_url)}" style="display:inline-block;background:#1565c0;'
        'color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:600;">'
        "Open your deal feed</a></div>"
        '<div style="margin-top:18px;font-size:11px;color:#90a4ae;line-height:1.5;">'
        "Informational only — not legal, financial, or real-estate advice. "
        f'<a href="{escape(unsubscribe_url)}" style="color:#90a4ae;">Unsubscribe</a>.<br>'
        f"{escape(postal_address)}</div></div></div>"
    )
