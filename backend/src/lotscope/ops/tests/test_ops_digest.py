from datetime import UTC, datetime

from lotscope.ops.digest import (
    OpsAlertContent,
    OpsDigestContent,
    OpsMarketLine,
    ops_alert_subject,
    ops_digest_subject,
    render_ops_alert_text,
    render_ops_digest_html,
    render_ops_digest_text,
)

_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def _content() -> OpsDigestContent:
    return OpsDigestContent(
        markets=[
            OpsMarketLine(
                market_code="phl",
                name="Philadelphia",
                health_status="red",
                red=[("rtt_summary", "Last run failed.")],
                amber=[("permits", "Overdue — last success 2 days ago.")],
                blockers=[("File the RTKL request", "operator")],
            )
        ],
        generated_at=_NOW,
    )


def test_digest_subject_counts_red_feeds() -> None:
    assert ops_digest_subject(_content()) == "LotScope ops — 1 red feed"


def test_digest_text_lists_reasons_and_ops_link() -> None:
    text = render_ops_digest_text(_content(), ops_url="https://app.test/admin/ops")
    assert "RED  rtt_summary: Last run failed." in text
    assert "amber permits" in text
    assert "blocked File the RTKL request (owner: operator)" in text
    assert "https://app.test/admin/ops" in text


def test_digest_html_escapes_content() -> None:
    dirty = OpsDigestContent(
        markets=[
            OpsMarketLine(
                market_code="x",
                name="A & B <lab>",
                health_status="amber",
                amber=[("d", "reason <b>")],
            )
        ],
        generated_at=_NOW,
    )
    html = render_ops_digest_html(dirty, ops_url="https://app.test/admin/ops")
    assert "A &amp; B &lt;lab&gt;" in html
    assert "<lab>" not in html


def test_alert_subject_and_text() -> None:
    content = OpsAlertContent(
        jobs=[("PHL · opa", "phl", "timeout")],
        datasets=[("phl", "opa_properties_public", "connection refused")],
    )
    assert ops_alert_subject(content) == "LotScope ops alert — 2 new failures"
    text = render_ops_alert_text(content, ops_url="https://app.test/admin/ops")
    assert "JOB [phl] PHL · opa: timeout" in text
    assert "DATASET [phl] opa_properties_public: connection refused" in text
