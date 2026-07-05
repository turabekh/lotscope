from datetime import UTC, date, datetime
from typing import Any

from lotscope.assessment.schemas import AssessmentResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.reports.appeal_packet import appeal_packet_filename, render_appeal_packet_pdf
from lotscope.valuation.schemas import CompResult, ValuationResult

_NOW = datetime(2026, 7, 4, tzinfo=UTC)


def _detail(**overrides: Any) -> ParcelDetail:
    base: dict[str, Any] = dict.fromkeys(ParcelDetail.model_fields)
    base["parcel_number"] = "000000001"
    base.update(overrides)
    base["market_code"] = "phl"
    base["local_key"] = str(base["parcel_number"]).split(":")[-1]
    return ParcelDetail(**base)


def _assessment(**overrides: Any) -> AssessmentResult:
    base: dict[str, Any] = {
        "parcel_number": "000000001",
        "status": "over_assessed",
        "assessed_market_value": 300000.0,
        "market_estimate": 220000.0,
        "market_low": 200000.0,
        "market_high": 240000.0,
        "gap": -80000.0,
        "gap_pct": -0.27,
        "over_assessed_amount": 80000.0,
        "estimated_annual_tax_savings": 1120.0,
        "tax_rate": 0.013998,
        "confidence": "high",
        "reasons": ["Assessed at $300,000 versus a modeled market value of $220,000."],
        "disclaimer": "Informational estimate only, not tax or legal advice.",
        "sources": [{"source": "opa_properties_public"}],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return AssessmentResult(**base)


def _valuation() -> ValuationResult:
    return ValuationResult(
        parcel_number="000000001",
        estimate=220000.0,
        low=200000.0,
        high=240000.0,
        price_per_sqft=180.0,
        confidence="high",
        comp_count=2,
        coefficient_of_variation=0.08,
        comps=[
            CompResult(
                parcel_number="000000002",
                address="2 Market St",
                distance_ft=120.0,
                sale_price=215000.0,
                sale_date=date(2025, 4, 1),
                lot_area_sqft=1200.0,
                price_per_sqft=179.0,
            )
        ],
        reasons=[],
        sources=[{"source": "rtt_summary"}],
        computed_at=_NOW,
    )


def test_packet_is_valid_pdf_with_comps() -> None:
    pdf = render_appeal_packet_pdf(
        detail=_detail(address="1 Main St"),
        assessment=_assessment(),
        valuation=_valuation(),
        generated_at=_NOW,
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1200


def test_packet_renders_without_comps() -> None:
    pdf = render_appeal_packet_pdf(
        detail=_detail(address="1 Main St"),
        assessment=_assessment(status="unknown", market_estimate=None),
        valuation=None,
        generated_at=_NOW,
    )
    assert pdf[:4] == b"%PDF"


def test_packet_filename_includes_parcel() -> None:
    assert appeal_packet_filename("000000001") == "lotscope-assessment-review-000000001.pdf"
