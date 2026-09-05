import io
from datetime import UTC, date, datetime

from pypdf import PdfReader

from lotscope.buyers.derivation import RepeatBuyer, RepeatPurchase
from lotscope.packet.schemas import PacketLot, RedFlag
from lotscope.reports.letter import (
    LetterContext,
    LetterPurchase,
    letter_filename,
    render_buyer_letter,
)
from lotscope.reports.letter_copy import LETTER_COPY

NOW = datetime(2026, 9, 5, tzinfo=UTC)


def _buyer(**overrides: object) -> RepeatBuyer:
    base: dict[str, object] = {
        "buyer_key": "ACME HOLDINGS LLC",
        "display_name": "Acme Holdings LLC",
        "purchase_count": 7,
        "total_consideration": 210_000.0,
        "purchases": (RepeatPurchase("phl:1", "1 TEST ST", date(2026, 3, 1), 30_000.0),),
        "mailing_address": "1 MAIN ST PHILADELPHIA PA 19100",
        "mailing_address_sources": 4,
        "owned_parcels": 6,
    }
    base.update(overrides)
    return RepeatBuyer(**base)  # type: ignore[arg-type]


def _lot() -> PacketLot:
    return PacketLot(
        parcel_number="phl:1",
        address="1 TEST ST",
        is_scheduled=False,
        is_vacant=True,
        lot_area_sqft=690.0,
        zoning_code="RSA-5",
        can_build_by_right=False,
        by_right_units=1,
        dimensional_reason="Lot area 690 sqft is below the 1440 sqft minimum for RSA-5.",
        provision_id="14-701(2)",
        max_allowable_offer=41_000.0,
        red_flags=[
            RedFlag(
                code="tax_delinquent",
                label="Tax delinquency",
                detail="$8,803 owed, recorded against HB HOLDING COMPANY LLC.",
                severity="high",
                source="tax_status",
                source_url="https://opendataphilly.org/datasets/real-estate-tax-delinquencies/",
            )
        ],
        verdict="LOOK",
        verdict_reason="",
        graded_as="build",
        grade_rule="build",
        computed_at=NOW,
    )


def _context(**overrides: object) -> LetterContext:
    base: dict[str, object] = {
        "buyer": _buyer(),
        "purchases": [
            LetterPurchase("phl:1", "1 TEST ST", date(2026, 3, 1), 30_000.0, _lot()),
        ],
        "window_months": 24,
        "register_url": "https://parcelphl.online/register",
        "invite_url": None,
        "invite_code": "JK4W4ZKZ",
        "generated_at": NOW,
        "sources": [("Recorded deeds (rtt_summary)", "https://example.test/rtt")],
    }
    base.update(overrides)
    return LetterContext(**base)  # type: ignore[arg-type]


def _text(context: LetterContext) -> str:
    reader = PdfReader(io.BytesIO(render_buyer_letter(context)))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def test_the_letter_has_two_pages_and_names_the_buyer() -> None:
    reader = PdfReader(io.BytesIO(render_buyer_letter(_context())))

    assert len(reader.pages) == 2
    assert "Acme Holdings LLC" in (reader.pages[0].extract_text() or "")


def test_page_one_grades_the_purchase_and_sources_every_figure() -> None:
    text = _text(_context())

    assert "1 TEST ST" in text
    assert "2026-03-01" in text
    assert "$30,000" in text
    assert "no, a variance is needed" in text
    assert "below the 1440 sqft minimum" in text
    assert "$41,000" in text
    assert "Tax delinquency" in text
    assert "HB HOLDING COMPANY LLC" in text
    assert "real-estate-tax-delinquencies" in text
    assert "rtt_summary" in text


def test_page_two_offers_the_packet_and_shows_the_code_when_there_is_no_email() -> None:
    text = _text(_context())

    assert LETTER_COPY["offer_heading"] in text
    assert "JK4W4ZKZ" in text
    assert "We do not have an email address for you" in text
    assert "not a broker, lender or law firm" in text


def test_an_invite_link_replaces_the_code_when_an_email_is_known() -> None:
    text = _text(
        _context(invite_url="https://parcelphl.online/register?invite=abc", invite_code=None)
    )

    assert "register?invite=abc" in text
    assert "JK4W4ZKZ" not in text


def test_a_purchase_we_could_not_grade_says_so_rather_than_inventing_a_figure() -> None:
    text = _text(
        _context(purchases=[LetterPurchase("phl:9", "9 GONE ST", date(2026, 1, 4), 5_000.0, None)])
    )

    assert "9 GONE ST" in text
    assert LETTER_COPY["unavailable"] in text


def test_the_copy_lives_in_one_editable_template() -> None:
    assert LETTER_COPY["heading"]
    assert "{purchase_count}" in LETTER_COPY["intro"]
    assert "{window_months}" in LETTER_COPY["intro"]
    assert "{register_url}" in LETTER_COPY["code_intro"]


def test_the_filename_is_derived_from_the_buyer_key() -> None:
    assert letter_filename("ACME HOLDINGS, L.L.C.") == "lotscope-letter-acme-holdings-l-l-c.pdf"
