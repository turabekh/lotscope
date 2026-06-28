from lotscope.notifications.digest import (
    DigestChange,
    DigestContent,
    DigestParcel,
    digest_subject,
    render_digest_html,
    render_digest_text,
)

_CONTENT = DigestContent(
    parcels=[
        DigestParcel(
            parcel_number="000000001",
            address="123 Main St",
            changes=[
                DigestChange("Now flagged for sheriff sale", "high"),
                DigestChange("Tax owed +$5,000", "medium"),
            ],
        ),
        DigestParcel(
            parcel_number="000000002",
            address=None,
            changes=[DigestChange("Opportunity 60 → 70", "info")],
        ),
    ]
)


def test_subject_counts_updates_and_lots() -> None:
    assert digest_subject(_CONTENT) == "3 updates on 2 watched lots"


def test_subject_singular() -> None:
    content = DigestContent(parcels=[DigestParcel("1", "A", [DigestChange("x", "info")])])
    assert digest_subject(content) == "1 update on 1 watched lot"


def test_html_includes_changes_links_and_compliance() -> None:
    html = render_digest_html(
        _CONTENT,
        watchlist_url="https://app.test/watchlist",
        unsubscribe_url="https://api.test/digests/unsubscribe?token=abc",
        postal_address="LotScope, Philadelphia PA",
    )
    assert "123 Main St" in html
    assert "Now flagged for sheriff sale" in html
    assert "https://app.test/watchlist" in html
    assert "unsubscribe?token=abc" in html
    assert "LotScope, Philadelphia PA" in html
    assert "000000002" in html  # falls back to parcel number when no address


def test_html_escapes_addresses() -> None:
    content = DigestContent(
        parcels=[DigestParcel("1", "<script>x</script>", [DigestChange("y", "info")])]
    )
    html = render_digest_html(
        content,
        watchlist_url="https://app.test/watchlist",
        unsubscribe_url="https://api.test/u",
        postal_address="addr",
    )
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_text_alternative_lists_changes_and_unsubscribe() -> None:
    text = render_digest_text(
        _CONTENT,
        watchlist_url="https://app.test/watchlist",
        unsubscribe_url="https://api.test/u",
        postal_address="addr",
    )
    assert "123 Main St" in text
    assert "- Tax owed +$5,000" in text
    assert "Unsubscribe: https://api.test/u" in text
