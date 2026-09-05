import io
from datetime import UTC, date, datetime

from pypdf import PdfReader

from lotscope.buybox.schemas import BuyBoxRead, BuyBoxWrite
from lotscope.packet.compose import LotInputs, compose_packet
from lotscope.packet.render import packet_filename, render_packet_pdf
from lotscope.packet.schemas import DataAsOf, PacketComp, PacketModel

SALE_DATE = date(2026, 9, 16)
GENERATED_AT = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)


def _buy_box() -> BuyBoxRead:
    return BuyBoxRead.model_validate(
        {
            **BuyBoxWrite(max_bid=95_000).model_dump(),
            "user_id": 1,
            "is_configured": True,
            "created_at": GENERATED_AT,
            "updated_at": GENERATED_AT,
        }
    )


def _packet() -> PacketModel:
    comps = (
        PacketComp(
            parcel_number="phl:c1",
            address="10 COMP ST",
            sale_date=date(2026, 4, 2),
            sale_price=245_000.0,
            reason="Finished rowhouse 300 ft away, sold five months ago.",
            source="rtt_summary",
            source_url="https://opendataphilly.org/datasets/real-estate-transfers/",
        ),
    )
    lots = [
        LotInputs(
            parcel_number="phl:bid",
            address="1500 BID ST",
            case_number="2609-001",
            sale_type="Tax",
            sale_date=SALE_DATE,
            opening_bid=8_000.0,
            status="Scheduled - Tax",
            plaintiff="City of Philadelphia",
            is_vacant=True,
            lot_area_sqft=1_100.0,
            zoning_code="RSA-5",
            overlays=("/NCA",),
            can_build_by_right=True,
            by_right_units=1,
            dimensional_reason="16 ft frontage meets the RSA-5 minimum of 16 ft.",
            provision_id="14-701(2)",
            max_allowable_offer=62_000.0,
            est_margin=0.31,
            comps=comps,
        ),
        LotInputs(
            parcel_number="phl:look",
            address="1502 LOOK ST",
            case_number="2609-002",
            sale_date=SALE_DATE,
            status="Postponed",
            is_vacant=True,
            lot_area_sqft=900.0,
            zoning_code="RSA-5",
            can_build_by_right=True,
            max_allowable_offer=40_000.0,
            est_margin=0.31,
            is_delinquent=True,
            total_due=14_000.0,
            delinquency_owner="ACME HOLDINGS LLC",
            comps=comps,
        ),
        LotInputs(
            parcel_number="phl:pass",
            address="1504 PASS ST",
            sale_date=SALE_DATE,
            is_vacant=True,
            lot_area_sqft=300.0,
            zoning_code="RSA-5",
            can_build_by_right=True,
            max_allowable_offer=20_000.0,
            est_margin=0.05,
        ),
        LotInputs(
            parcel_number="phl:house",
            address="1506 HOUSE ST",
            sale_date=SALE_DATE,
            is_vacant=False,
        ),
    ]
    return compose_packet(
        sale_date=SALE_DATE,
        buy_box=_buy_box(),
        required_margin=0.20,
        lots=lots,
        data_as_of=[
            DataAsOf(
                source="opa_properties_public",
                source_url="https://opendataphilly.org/datasets/",
                fetched_at=GENERATED_AT,
            )
        ],
        generated_at=GENERATED_AT,
        today=date(2026, 9, 5),
    )


def test_the_pdf_opens_and_has_a_page_for_the_summary_and_each_kept_lot() -> None:
    packet = _packet()
    data = render_packet_pdf(packet)

    assert data.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1 + len(packet.lots)


def test_the_first_page_carries_the_header_counts_and_every_lot_row() -> None:
    text = _first_page_text()

    assert "Sale Packet - 2026-09-16" in text
    assert "4 listings" in text
    assert "3 vacant" in text
    assert "2 pass your buy box" in text
    for parcel in ("phl:bid", "phl:look", "phl:pass"):
        assert parcel in text


def test_every_red_flag_and_comp_prints_its_source_url() -> None:
    text = _all_text()

    assert "opendataphilly.org/datasets/real-estate-transfers/" in text
    assert "opendataphilly.org/datasets/real-estate-tax-delinquencies/" in text
    assert "ACME HOLDINGS LLC" in text


def test_the_pdf_names_water_and_gas_among_what_it_cannot_see() -> None:
    text = _all_text()

    assert "Water and sewer liens" in text
    assert "Gas liens" in text


def test_every_packet_warns_that_the_opening_bid_is_nominal() -> None:
    packet = _packet()
    text = _all_text()

    assert "nominal on tax sales" in text
    assert "expect to compete" in text
    for lot in packet.lots:
        assert lot.opening_bid_note in lot.verify_before_bidding
        assert "nominal on tax sales" in lot.opening_bid_note
    assert packet.verify_before_bidding[0] == packet.lots[0].opening_bid_note


def test_passed_lots_appear_in_the_appendix_with_their_reason() -> None:
    text = _all_text()

    assert "Passed lots, and why" in text
    assert "phl:pass" in text
    assert "Not vacant, so not screened" in text


def test_the_filename_names_the_sale_and_the_buyer() -> None:
    assert packet_filename("2026-09-16", 42) == "lotscope-sale-packet-2026-09-16-u42.pdf"


def _reader() -> PdfReader:
    return PdfReader(io.BytesIO(render_packet_pdf(_packet())))


def _first_page_text() -> str:
    return _reader().pages[0].extract_text() or ""


def _all_text() -> str:
    return "\n".join((page.extract_text() or "") for page in _reader().pages)
