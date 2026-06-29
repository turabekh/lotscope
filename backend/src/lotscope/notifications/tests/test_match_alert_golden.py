import os
from pathlib import Path

from lotscope.notifications.digest import (
    MatchAlertContent,
    MatchAlertParcel,
    MatchAlertSearch,
    render_match_alert_html,
    render_match_alert_text,
)

_GOLDEN_DIR = Path(__file__).parent / "golden"
_RENDER_KWARGS = {
    "searches_url": "https://app.lotscope.phl/saved-searches",
    "unsubscribe_url": "https://api.lotscope.phl/digests/unsubscribe?token=abc123",
    "postal_address": "LotScope PHL, 1500 Market St, Philadelphia, PA 19102",
}

_CONTENT = MatchAlertContent(
    searches=[
        MatchAlertSearch(
            name="Vacant RSA5 under $60k",
            parcels=[
                MatchAlertParcel("888000123", "1432 N MARSTON ST", 78),
                MatchAlertParcel("888000124", "2210 W SUSQUEHANNA AVE", 64),
                MatchAlertParcel("888000125", None, None),
            ],
        ),
        MatchAlertSearch(
            name="Tax-delinquent CMX2 in 19121",
            parcels=[MatchAlertParcel("771004500", "1900 CECIL B MOORE AVE", 71)],
        ),
    ]
)


def _check(filename: str, rendered: str) -> None:
    path = _GOLDEN_DIR / filename
    if os.environ.get("LOTSCOPE_UPDATE_GOLDEN"):
        _GOLDEN_DIR.mkdir(exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
    expected = path.read_text(encoding="utf-8")
    assert rendered == expected, (
        f"{filename} drifted from golden; rerun with LOTSCOPE_UPDATE_GOLDEN=1 to refresh."
    )


def test_match_alert_html_matches_golden() -> None:
    _check("match_alert.html", render_match_alert_html(_CONTENT, **_RENDER_KWARGS))


def test_match_alert_text_matches_golden() -> None:
    _check("match_alert.txt", render_match_alert_text(_CONTENT, **_RENDER_KWARGS))
