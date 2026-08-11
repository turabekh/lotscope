import re
import zlib
from datetime import UTC, datetime
from typing import Any

from lotscope.ai.schemas import ParcelReportResult, ReportSection
from lotscope.assemblage.schemas import AdjacentLot, AssemblageResult, AssemblageSummary
from lotscope.checklist.schemas import ChecklistItem, ChecklistSummary, ParcelChecklist
from lotscope.distress.schemas import DistressFactor, DistressResult
from lotscope.parcels.schemas import ParcelDetail
from lotscope.reports.dossier import dossier_filename, render_dossier_pdf
from lotscope.verdict.schemas import VerdictResult
from lotscope.zoning.schemas import BuildabilityResult

_NOW = datetime(2026, 6, 28, tzinfo=UTC)


def _detail(**overrides: Any) -> ParcelDetail:
    base: dict[str, Any] = dict.fromkeys(ParcelDetail.model_fields)
    base["parcel_number"] = "000000001"
    base.update(overrides)
    base["market_code"] = "phl"
    base["local_key"] = str(base["parcel_number"]).split(":")[-1]
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
        verdict_version="v2",
        buildability_score=70,
        opportunity_score=68,
        summary="RSD-3: buildable by-right (1 unit); 2 risk flags; MAO $95,000 (underpriced).",
        can_build_by_right=True,
        by_right_units=1,
        max_height_ft=38,
        needs_variance=False,
        buildable_area_sqft=1680,
        value_estimate_low=None,
        value_estimate_high=None,
        value_confidence=None,
        assessment_market_gap=None,
        arv=480000,
        est_profit=72000,
        est_margin=0.15,
        max_allowable_offer=95000,
        deal_score=62,
        is_underpriced=True,
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
        version="v2",
        profile_id="philly-distress-v1",
        factors=[DistressFactor(code="sheriff_sale", label="Sheriff-sale exposure", weight=30)],
        sources=[],
        computed_at=_NOW,
    )
    checklist = ParcelChecklist(
        parcel_number="000000001",
        items=[
            ChecklistItem(
                code="zoning",
                label="Zoning conformance",
                category="Zoning & buildability",
                status="potential_issue",
                detail="A variance is likely required.",
                source="zoning",
            ),
            ChecklistItem(
                code="liens_taxes",
                label="Liens & taxes",
                category="Liens & taxes",
                status="fail",
                detail="$31,000 owed.",
                source="tax_status",
            ),
            ChecklistItem(
                code="flood",
                label="Flood & environmental",
                category="Flood & environmental",
                status="pass",
                detail="Not in a mapped flood zone.",
            ),
        ],
        summary=ChecklistSummary(passed=1, warnings=1, failures=1, info=0, ready=False),
        computed_at=_NOW,
    )
    pdf = render_dossier_pdf(
        detail=_detail(
            address="1 Main St", owner="OWNER A", base_zoning_code="RSD-3", is_vacant=True
        ),
        verdict=verdict,
        assemblage=assemblage,
        distress=distress,
        checklist=checklist,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1500


def test_dossier_with_report_renders_memo_section() -> None:
    report = ParcelReportResult(
        parcel_number="000000001",
        headline="Underpriced by-right rowhouse lot.",
        sections=[
            ReportSection(heading="Overview", body="A vacant RSA-5 lot with by-right potential."),
            ReportSection(heading="Risks", body="Tax delinquency is on record."),
        ],
        recommendation="Consider a direct offer near the max allowable offer.",
        confidence="medium",
        is_informational=True,
        sources=[],
        computed_at=_NOW,
    )
    common: dict[str, Any] = {
        "detail": _detail(address="1 Main St"),
        "verdict": None,
        "assemblage": None,
        "distress": None,
        "generated_at": _NOW,
        "disclaimer": "Informational only.",
    }
    with_report = render_dossier_pdf(report=report, **common)
    without_report = render_dossier_pdf(**common)

    assert with_report[:4] == b"%PDF"
    assert len(with_report) > len(without_report)


def test_dossier_filename() -> None:
    assert dossier_filename("000000001") == "lotscope-dossier-000000001.pdf"


def test_negative_gap_reads_as_a_negative_amount() -> None:
    from lotscope.reports.dossier import _money

    assert _money(-31099) == "-$31,099"
    assert _money(31099) == "$31,099"
    assert _money(None) == "-"


def test_dossier_carries_page_furniture_and_sources() -> None:
    verdict = VerdictResult(
        parcel_number="000000001",
        verdict_version="v8",
        buildability_score=50,
        opportunity_score=54,
        summary="RSA-3: variance likely.",
        can_build_by_right=False,
        by_right_units=1,
        max_height_ft=38,
        needs_variance=True,
        buildable_area_sqft=0,
        value_estimate_low=9723,
        value_estimate_high=195204,
        value_confidence=0.3,
        assessment_market_gap=-31099,
        arv=180000,
        est_profit=None,
        est_margin=None,
        max_allowable_offer=0,
        deal_score=None,
        is_underpriced=None,
        risk_score=10,
        risk_flags=[],
        sources=[
            {
                "dimension": "buildability",
                "sources": [
                    {"source": "zoning_district", "method": "spatial"},
                    {"source": "zoning_standard", "version": "title14-quickguide-2026-02"},
                ],
            }
        ],
        computed_at=_NOW,
    )
    pdf = render_dossier_pdf(
        detail=_detail(address="5346 Spruce St", market_code="phl"),
        verdict=verdict,
        assemblage=None,
        distress=None,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 2000


def test_a_zero_buildable_area_carries_its_reasoning() -> None:
    from lotscope.zoning.schemas import BuildabilityResult

    verdict = VerdictResult(
        parcel_number="000000001",
        verdict_version="v8",
        buildability_score=20,
        opportunity_score=54,
        summary="RSA-3: variance likely.",
        can_build_by_right=False,
        by_right_units=1,
        max_height_ft=38,
        needs_variance=True,
        buildable_area_sqft=0,
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
        risk_score=10,
        risk_flags=[],
        sources=[],
        computed_at=_NOW,
    )
    buildability = BuildabilityResult(
        parcel_number="000000001",
        district_code="RSA-3",
        district_method="spatial",
        cited_section="Title 14 RSA-3",
        conforming=False,
        can_build_by_right=False,
        needs_variance=True,
        by_right_units=1,
        max_height_ft=38,
        buildable_area_sqft=0,
        buildability_score=20,
        confidence="high",
        reasons=["Lot width 16 ft is below the 25 ft minimum for RSA-3."],
        sources=[],
        computed_at=_NOW,
    )
    with_reasons = render_dossier_pdf(
        detail=_detail(address="5346 Spruce St"),
        verdict=verdict,
        buildability=buildability,
        assemblage=None,
        distress=None,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    without = render_dossier_pdf(
        detail=_detail(address="5346 Spruce St"),
        verdict=verdict,
        buildability=None,
        assemblage=None,
        distress=None,
        generated_at=_NOW,
        disclaimer="Informational only.",
    )
    assert with_reasons[:4] == b"%PDF"
    assert len(with_reasons) > len(without)


def _pdf_text(raw: bytes) -> str:
    streams = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        try:
            streams.append(zlib.decompress(match.group(1)).decode("latin-1"))
        except zlib.error:
            continue
    return "\n".join(streams)


def _verdict_for_units(**overrides: Any) -> VerdictResult:
    base: dict[str, Any] = {
        "parcel_number": "000000001",
        "verdict_version": "v8",
        "buildability_score": 70.0,
        "opportunity_score": 68.0,
        "summary": "RSA-5",
        "can_build_by_right": True,
        "by_right_units": 2,
        "max_height_ft": 38.0,
        "needs_variance": False,
        "buildable_area_sqft": 500.0,
        "value_estimate_low": 100000.0,
        "value_estimate_high": 200000.0,
        "value_confidence": 0.6,
        "assessment_market_gap": None,
        "arv": None,
        "est_profit": None,
        "est_margin": None,
        "max_allowable_offer": None,
        "deal_score": None,
        "is_underpriced": None,
        "risk_score": 10.0,
        "risk_flags": [],
        "sources": [],
        "computed_at": _NOW,
    }
    base.update(overrides)
    return VerdictResult(**base)


def _render(verdict: VerdictResult, buildability: BuildabilityResult | None = None) -> str:
    return _pdf_text(
        render_dossier_pdf(
            detail=_detail(address="1 Main St"),
            verdict=verdict,
            assemblage=None,
            distress=None,
            generated_at=_NOW,
            disclaimer="Informational only.",
            buildability=buildability,
        )
    )


def test_report_does_not_call_units_by_right_when_a_variance_is_needed() -> None:
    text = _render(_verdict_for_units(can_build_by_right=False, needs_variance=True))

    assert "Units if a variance is granted" in text
    assert "By-right units" not in text


def test_report_shows_no_unit_count_for_a_master_plan_district() -> None:
    fields: dict[str, Any] = dict.fromkeys(BuildabilityResult.model_fields)
    fields.update(
        parcel_number="000000001",
        district_code="SP-PO-A",
        can_build_by_right=False,
        needs_variance=None,
        by_right_units=None,
        requires_master_plan=True,
        reasons=[],
        sources=[],
        critical_unknowns=[],
        confidence="low",
        buildability_score=25.0,
        computed_at=_NOW,
    )
    buildability = BuildabilityResult(**fields)
    text = _render(
        _verdict_for_units(can_build_by_right=False, needs_variance=None, by_right_units=3),
        buildability,
    )

    assert "none - master plan required" in text.lower()
    assert "By-right units: 3" not in text


def test_report_keeps_the_plain_label_for_a_by_right_lot() -> None:
    text = _render(_verdict_for_units())

    assert "By-right units" in text
    assert "Units if a variance is granted" not in text


def test_report_does_not_call_a_low_confidence_estimate_a_nearby_comp_read() -> None:
    text = _render(_verdict_for_units(value_confidence=0.3))

    assert "low confidence" in text
    assert "rough guide" in text
    assert "Estimated from recent recorded comparable sales nearby" not in text


def test_report_states_the_support_plainly_when_confidence_is_high() -> None:
    text = _render(_verdict_for_units(value_confidence=0.9))

    assert "high confidence" in text
    assert "recent recorded comparable sales nearby" in text
    assert "rough guide" not in text


def test_report_does_not_imply_a_weak_estimate_when_there_is_none() -> None:
    text = _render(
        _verdict_for_units(value_estimate_low=None, value_estimate_high=None, value_confidence=None)
    )

    assert "Not enough comps" in text
    assert "rough guide" not in text
