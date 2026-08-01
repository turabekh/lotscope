from datetime import UTC, date, datetime

import pytest

from lotscope.core.errors import MissingEconomicsError
from lotscope.reports.loi import (
    LOI_DISCLAIMER,
    LoiDocument,
    LoiSigner,
    LoiTerms,
    compose_loi,
    loi_filename,
    render_loi_pdf,
)
from lotscope.valuation.schemas import CompResult, ValuationResult

_NOW = datetime(2026, 7, 12, tzinfo=UTC)


def _compose(
    mao: float | None, override: float | None = None, *, has_comps: bool = True
) -> LoiDocument:
    return compose_loi(
        parcel_number="phl:123",
        local_key="123",
        address="123 MAIN ST",
        max_allowable_offer=mao,
        offer_price_override=override,
        terms=LoiTerms(expiration=date(2026, 7, 19)),
        signer=LoiSigner(entity_name="ACME LLC"),
        has_comps=has_comps,
        generated_at=_NOW,
    )


def test_offer_price_defaults_to_mao() -> None:
    doc = _compose(100000.0)
    assert doc.offer_price == 100000.0
    assert doc.mao_framing is True
    assert "Maximum Allowable Offer" in doc.price_provenance


def test_override_price_records_override_provenance() -> None:
    doc = _compose(100000.0, 90000.0)
    assert doc.offer_price == 90000.0
    assert doc.mao_framing is True
    assert "overriding" in doc.price_provenance


def test_manual_price_without_mao_is_user_supplied() -> None:
    doc = _compose(None, 80000.0)
    assert doc.offer_price == 80000.0
    assert doc.mao_framing is False
    assert "user-supplied" in doc.price_provenance


def test_missing_economics_raises() -> None:
    with pytest.raises(MissingEconomicsError):
        _compose(None, None)


def test_appendix_present_iff_comps() -> None:
    assert _compose(100000.0, has_comps=True).has_appendix is True
    assert _compose(100000.0, has_comps=False).has_appendix is False


def test_disclaimer_always_present() -> None:
    assert _compose(100000.0).disclaimer == LOI_DISCLAIMER
    assert _compose(None, 50000.0).disclaimer == LOI_DISCLAIMER


def test_term_defaults() -> None:
    terms = LoiTerms()
    assert terms.all_cash is True
    assert terms.as_is is True
    assert terms.earnest_money == 1000.0
    assert terms.close_days == 30
    assert terms.inspection_days == 10


def _valuation() -> ValuationResult:
    return ValuationResult(
        parcel_number="phl:123",
        estimate=120000.0,
        low=100000.0,
        high=140000.0,
        price_per_sqft=80.0,
        confidence="medium",
        comp_count=2,
        coefficient_of_variation=0.2,
        comps=[
            CompResult(
                parcel_number="phl:900",
                address="900 " + "LONG STREET NAME " * 4,
                distance_ft=250.0,
                sale_price=95000.0,
                sale_date=date(2026, 3, 1),
                lot_area_sqft=1000.0,
                price_per_sqft=95.0,
            ),
        ],
        reasons=["Excluded 1 likely related-party sale."],
        sources=[{"package_deeds_excluded": True}],
        computed_at=_NOW,
    )


def test_render_pdf_with_appendix_smoke() -> None:
    doc = _compose(100000.0, has_comps=True)
    pdf = render_loi_pdf(doc, _valuation())
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_render_pdf_without_valuation_smoke() -> None:
    doc = compose_loi(
        parcel_number="phl:1",
        local_key="1",
        address="A VERY " + "LONG " * 30 + "ADDRESS",
        max_allowable_offer=None,
        offer_price_override=42000.0,
        terms=LoiTerms(),
        signer=LoiSigner(entity_name="X" * 200, signer_name="Y" * 200),
        has_comps=False,
        generated_at=_NOW,
    )
    pdf = render_loi_pdf(doc, None)
    assert pdf.startswith(b"%PDF")


def test_loi_filename_slugs_parcel() -> None:
    assert loi_filename(_compose(100000.0)) == "lotscope-loi-phl-123.pdf"


def test_an_open_offer_says_so_rather_than_printing_a_dash() -> None:
    from lotscope.reports.loi import LoiTerms, _terms_lines

    lines = dict(_terms_lines(LoiTerms(expiration=None)))
    assert lines["Offer valid through"] == "Open until withdrawn in writing"


def test_the_letter_carries_signature_lines_for_both_parties() -> None:
    from datetime import UTC, datetime

    from lotscope.reports.loi import LoiDocument, LoiSigner, LoiTerms, render_loi_pdf

    document = LoiDocument(
        parcel_number="phl:1",
        local_key="1",
        address="5346 Spruce St",
        offer_price=45000.0,
        price_provenance="Offer price is the LotScope Maximum Allowable Offer of $45,000.",
        mao_framing=True,
        terms=LoiTerms(),
        signer=LoiSigner(entity_name="Acme Land LLC", signer_name="T. Holmirzaev"),
        has_appendix=False,
        disclaimer="Informational only.",
        generated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    with_block = render_loi_pdf(document, None)
    assert with_block[:4] == b"%PDF"
    assert len(with_block) > 1500
