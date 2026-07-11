from dataclasses import dataclass, field
from datetime import datetime
from html import escape

_STATUS_COLOR = {"red": "#c62828", "amber": "#ef6c00", "green": "#2e7d32", "unknown": "#616161"}


@dataclass(frozen=True)
class OpsMarketLine:
    market_code: str
    name: str
    health_status: str
    red: list[tuple[str, str]] = field(default_factory=list)
    amber: list[tuple[str, str]] = field(default_factory=list)
    blockers: list[tuple[str, str | None]] = field(default_factory=list)
    failures: list[tuple[str, str | None]] = field(default_factory=list)


@dataclass(frozen=True)
class OpsDigestContent:
    markets: list[OpsMarketLine]
    generated_at: datetime

    @property
    def red_count(self) -> int:
        return sum(len(line.red) for line in self.markets)

    @property
    def failure_count(self) -> int:
        return sum(len(line.failures) for line in self.markets)


@dataclass(frozen=True)
class OpsAlertContent:
    jobs: list[tuple[str, str | None, str | None]]
    datasets: list[tuple[str, str, str | None]]

    @property
    def total(self) -> int:
        return len(self.jobs) + len(self.datasets)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def ops_digest_subject(content: OpsDigestContent) -> str:
    reds = content.red_count
    fails = content.failure_count
    parts: list[str] = []
    if reds:
        parts.append(f"{reds} red feed{'' if reds == 1 else 's'}")
    if fails:
        parts.append(f"{fails} failure{'' if fails == 1 else 's'}")
    detail = ", ".join(parts) if parts else "attention needed"
    return f"LotScope ops — {detail}"


def render_ops_digest_text(content: OpsDigestContent, *, ops_url: str) -> str:
    lines = [f"LotScope fleet health — {_stamp(content.generated_at)}", ""]
    for line in content.markets:
        lines.append(f"{line.name} [{line.health_status}]")
        for dataset, reason in line.red:
            lines.append(f"  RED  {dataset}: {reason}")
        for dataset, reason in line.amber:
            lines.append(f"  amber {dataset}: {reason}")
        for label, error in line.failures:
            lines.append(f"  FAILED {label}: {error or 'see job history'}")
        for title, owner in line.blockers:
            owned = f" (owner: {owner})" if owner else ""
            lines.append(f"  blocked {title}{owned}")
        lines.append("")
    lines.append(f"Ops center: {ops_url}")
    return "\n".join(lines)


def render_ops_digest_html(content: OpsDigestContent, *, ops_url: str) -> str:
    blocks: list[str] = [
        '<h2 style="font:600 18px sans-serif;color:#0f4ba8">LotScope fleet health</h2>',
        f'<p style="font:12px sans-serif;color:#616161">{escape(_stamp(content.generated_at))}</p>',
    ]
    for line in content.markets:
        color = _STATUS_COLOR.get(line.health_status, "#616161")
        rows: list[str] = []
        for dataset, reason in line.red:
            rows.append(_row("RED", "#c62828", dataset, reason))
        for dataset, reason in line.amber:
            rows.append(_row("amber", "#ef6c00", dataset, reason))
        for label, error in line.failures:
            rows.append(_row("FAILED", "#c62828", label, error or "see job history"))
        for title, owner in line.blockers:
            suffix = f" (owner: {owner})" if owner else ""
            rows.append(_row("blocked", "#616161", title, suffix.strip() or "—"))
        blocks.append(
            f'<div style="margin:12px 0"><div style="font:600 14px sans-serif;color:{color}">'
            f"{escape(line.name)} · {escape(line.health_status)}</div>{''.join(rows)}</div>"
        )
    blocks.append(
        f'<p><a href="{escape(ops_url)}" style="color:#0f4ba8">Open the ops center</a></p>'
    )
    return "".join(blocks)


def _row(tag: str, color: str, name: str, detail: str) -> str:
    return (
        f'<div style="font:13px sans-serif;margin:2px 0">'
        f'<span style="color:{color};font-weight:600">{escape(tag)}</span> '
        f"<b>{escape(name)}</b> — {escape(detail)}</div>"
    )


def ops_alert_subject(content: OpsAlertContent) -> str:
    n = content.total
    return f"LotScope ops alert — {n} new failure{'' if n == 1 else 's'}"


def render_ops_alert_text(content: OpsAlertContent, *, ops_url: str) -> str:
    lines = ["New ingestion / job failures:", ""]
    for label, market, error in content.jobs:
        scope = f"[{market}] " if market else ""
        lines.append(f"  JOB {scope}{label}: {error or 'see job history'}")
    for market, dataset, detail in content.datasets:
        lines.append(f"  DATASET [{market}] {dataset}: {detail or 'ingest failed'}")
    lines.append("")
    lines.append(f"Ops center: {ops_url}")
    return "\n".join(lines)


def render_ops_alert_html(content: OpsAlertContent, *, ops_url: str) -> str:
    rows: list[str] = []
    for label, market, error in content.jobs:
        scope = f"[{market}] " if market else ""
        rows.append(_row("JOB", "#c62828", f"{scope}{label}", error or "see job history"))
    for market, dataset, detail in content.datasets:
        rows.append(_row("DATASET", "#c62828", f"[{market}] {dataset}", detail or "ingest failed"))
    link = f'<p><a href="{escape(ops_url)}" style="color:#0f4ba8">Open the ops center</a></p>'
    return (
        '<h2 style="font:600 18px sans-serif;color:#c62828">New failures</h2>'
        + "".join(rows)
        + link
    )
