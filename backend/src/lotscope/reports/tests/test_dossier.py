from datetime import UTC, datetime
from typing import Any

from lotscope.assemblage.schemas import AdjacentLot, AssemblageResult, AssemblageSummary
from lotscope.distress.schemas import DistressFactor, DistressResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.reports.dossier import dossier_filename, render_dossier_pdf
from lotscope.verdict.schemas import VerdictResult

_NOW = datetime(2026, 6, 28, tzinfo=UTC)


def _detail(**overrides: Any) -> ParcelDetail:
    base: dict[str, Any] = dict.fromkeys(ParcelDetail.model_fields)
    base["parcel_number"] = "000000001"
    base.update(overrides)
    return ParcelDetail(**base)


def test_minimal_dossier_is_valid_pdf() -> None:
    pdf = render_dossier_pdf(
        detail=_detail(address="1 Main St"),
        verdict=None,
        assemblage=None,
        distress=None,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 800


def test_full_dossier_renders_all_sections() -> None:
    verdict = VerdictResult(
        parcel_number="000000001",
        verdict_version="v1",
        buildability_score=70,
        opportunity_score=68,
        summary="RSD-3: buildable by-right (1 unit); 2 risk flags.",
        can_build_by_right=True,
        by_right_units=1,
        max_height_ft=38,
        needs_variance=False,
        buildable_area_sqft=1680,
        value_estimate_low=None,
        value_estimate_high=None,
        value_confidence=None,
        assessment_market_gap=None,
        arv=None,
        est_profit=None,
        est_margin=None,
        max_allowable_offer=None,
        deal_score=None,
        is_underpriced=None,
        risk_score=30,
        risk_flags=[
            {
                "code": "li_violations",
                "severity": "medium",
                "label": "L&I violations on record",
                "detail": "3 violation(s) on record - Dangerous, Interior.",
                "source": "li_event",
            }
        ],
        sources=[],
        computed_at=_NOW,
    )
    assemblage = AssemblageResult(
        parcel_number="000000001",
        potential="high",
        summary=AssemblageSummary(
            adjacent_count=2,
            candidate_count=2,
            combined_lot_area_sqft=3200,
            combined_frontage_ft=36,
            by_right_units_current=3,
            by_right_units_combined=6,
            units_basis="per_unit",
            has_same_owner_neighbor=False,
            has_city_owned_neighbor=False,
            has_vacant_neighbor=True,
        ),
        neighbors=[
            AdjacentLot(
                parcel_number="000000002",
                address="3 Main St",
                owner="OWNER B",
                base_zoning_code="RM-1",
                lot_area_sqft=1600,
                frontage_ft=18,
                market_value=90000,
                is_vacant=True,
                is_city_owned=False,
                same_owner=False,
                same_zoning=True,
                shared_boundary_ft=90,
                acquirability="vacant",
                is_candidate=True,
            )
        ],
        reasons=[],
        sources=[],
        computed_at=_NOW,
    )
    distress = DistressResult(
        parcel_number="000000001",
        score=60,
        tier="high",
        factors=[DistressFactor(code="sheriff_sale", label="Sheriff-sale exposure", weight=30)],
        sources=[],
        computed_at=_NOW,
    )
    pdf = render_dossier_pdf(
        detail=_detail(
            address="1 Main St", owner="OWNER A", base_zoning_code="RSD-3", is_vacant=True
        ),
        verdict=verdict,
        assemblage=assemblage,
        distress=distress,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1500


def test_dossier_filename() -> None:
    assert dossier_filename("000000001") == "lotscope-dossier-000000001.pdf"
