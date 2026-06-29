from lotscope.notifications.digest import (
    MatchAlertContent,
    MatchAlertParcel,
    MatchAlertSearch,
    match_alert_subject,
    render_match_alert_html,
    render_match_alert_text,
)

_CONTENT = MatchAlertContent(
    searches=[
        MatchAlertSearch(
            name="Vacant RSA-5 under $60k",
            parcels=[
                MatchAlertParcel("000000001", "123 Main St", 72),
                MatchAlertParcel("000000002", None, None),
            ],
        )
    ]
)


def test_subject_single_search() -> None:
    assert match_alert_subject(_CONTENT) == "2 new lots match “Vacant RSA-5 under $60k”"


def test_subject_multiple_searches_and_singular_lot() -> None:
    content = MatchAlertContent(
        searches=[
            MatchAlertSearch(name="A", parcels=[MatchAlertParcel("1", "x", None)]),
            MatchAlertSearch(name="B", parcels=[]),
        ]
    )
    assert match_alert_subject(content) == "1 new lot match 2 of your saved searches"


def test_text_lists_parcels_and_compliance() -> None:
    text = render_match_alert_text(
        _CONTENT,
        searches_url="https://app.example.com/saved-searches",
        unsubscribe_url="https://api.example.com/digests/unsubscribe?token=t",
        postal_address="1 Market St, Philadelphia PA",
    )
    assert "123 Main St — opportunity 72" in text
    assert "000000002" in text
    assert "not legal or financial advice" in text
    assert "https://app.example.com/saved-searches" in text


def test_html_escapes_and_includes_cta() -> None:
    content = MatchAlertContent(
        searches=[MatchAlertSearch(name="<script>", parcels=[MatchAlertParcel("1", "<b>", 5)])]
    )
    html = render_match_alert_html(
        content,
        searches_url="https://app.example.com/saved-searches",
        unsubscribe_url="https://api.example.com/u",
        postal_address="addr",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "Review saved searches" in html
