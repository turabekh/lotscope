from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.markets.models import Market
from lotscope.ops.models import MarketGateItem

GRADUATION = "graduation"
PARITY = "parity"

_SATISFIED_PARITY = frozenset({"pass", "honest_degradation"})

_HBG_GRADUATION: tuple[dict[str, Any], ...] = (
    {
        "status": "blocked",
        "title": "Standards verified; reviewer sign-off recorded, cap lifted, hbg recomputed "
        "at hbg-2026-verified",
        "owner": "operator",
        "evidence": "Standards corpus-complete + cap-lift mechanism built "
        "(make graduate-hbg-zoning), but still hbg-provisional-2026. Blocker: deliver the "
        "25-parcel packet, record sign-off, then run the cap-lift.",
    },
    {
        "status": "blocked",
        "title": "Corpus embedded; Ask-the-Parcel live with Harrisburg citations; "
        "cross-market isolation green",
        "owner": "operator",
        "evidence": "0 chunks embedded. Blocker: run the embed-load when the Voyage quota "
        "resets (buildability is unaffected).",
    },
    {
        "status": "met",
        "title": "Flood live; historic live; named-area (search) live",
        "evidence": "Historic (7 districts) and named-area (20 neighborhoods) live; flood live — "
        "3,200 city Flood_Parcels zones loaded 2026-07-10, risk scoring classifies 100/500-Year, "
        "180 hbg verdicts carry a flood flag. All three sub-conditions live on prod.",
    },
    {
        "status": "met",
        "qualifier": "repository only",
        "title": "Repository wired (live); upset/judicial pipeline armed",
        "evidence": "Repository list live — 191 city parcels from the 2026-06-25 CSV; dossier "
        "badge + Tax-sales repository tab live; monthly refresh registered. Upset/judicial "
        "pipeline still armed for the August list.",
    },
    {
        "status": "met",
        "title": "Comps at best-available; coverage reported",
        "evidence": "Reported (hbg-comps-coverage.md): 0 priced sales / 0 value estimates — the "
        "honest ceiling; AVM degrades correctly, weights not renormalized.",
    },
    {
        "status": "partial",
        "title": "Violations pipeline built; RTKL filed",
        "owner": "operator",
        "evidence": "Pipeline built + fixture-tested; RTKL request drafted. Blocker: file the "
        "RTKL request; on delivery, load + flip the note.",
    },
    {
        "status": "met",
        "title": "Checklist states truthful everywhere; RCO structural removal in; "
        "forced-sale surface market-aware",
        "evidence": "Distinct no_data_source / pending_load states; RCO removed for hbg; "
        "sheriff/tax-sale surface market-scoped + labelled (hidden until data — honest).",
    },
    {
        "status": "met",
        "title": "Full hbg recompute at final data; full Philadelphia regression; "
        "VERDICT_VERSION still v8",
        "evidence": "19,502 hbg verdicts at v8; Philadelphia byte-unchanged across all 7 slices.",
    },
)

_HBG_PARITY: tuple[dict[str, Any], ...] = (
    {
        "status": "pass",
        "title": "Parcels with spine + geometry",
        "threshold": "≥ 98%",
        "measured": "99.95% (owner + geom_local)",
    },
    {
        "status": "pass",
        "title": "Verdict coverage",
        "threshold": "≥ 95%",
        "measured": "100.0% (19,502 at v8)",
    },
    {
        "status": "honest_degradation",
        "title": "Usable comp for vacant parcels",
        "threshold": "≥ 60% or honest degradation",
        "measured": "0 priced comps — Dauphin open data has no sale price/date (deed refs only)",
        "qualifier": "verified (ADR-0054)",
    },
    {
        "status": "pass",
        "title": "Distress computed for flagged parcels",
        "threshold": "every flagged parcel",
        "measured": "RETSL adapter built + fixture-tested; no live list currently published "
        "(seasonal PDF) → 0 forced-sale-flagged; tax-exposure distress computes where data exists",
        "qualifier": "vacuously + documented follow-up",
    },
    {
        "status": "pass",
        "title": "Every checklist row live or explicit no-source",
        "threshold": "all rows",
        "measured": "zoning, liens/taxes, access, ownership, valuation live; L&I, overlays, "
        "flood render 'no data source for this market'",
    },
    {
        "status": "pass",
        "title": "25-parcel golden set",
        "threshold": "delivered",
        "measured": "docs/wave0-hbg-25parcel-packet.md (all 9 districts)",
        "qualifier": "reviewer sign-off pending",
    },
)

_PGH_PARITY: tuple[dict[str, Any], ...] = (
    {
        "status": "pass",
        "title": "Parcels with spine + geometry",
        "threshold": "≥ 98%",
        "measured": "99.93% (143,257 / 143,355 with geom_local)",
    },
    {
        "status": "pass",
        "title": "Verdict coverage",
        "threshold": "≥ 95%",
        "measured": "100.0% (143,355 / 143,355 at v8)",
    },
    {
        "status": "honest_degradation",
        "title": "Usable comp for vacant parcels",
        "threshold": "≥ 60% or honest degradation",
        "measured": "3 validated vacant-land sales in the 3-yr window (83 all-time; VALID-SALE "
        "filter) — AVM runs low/no-confidence for vacant land by construction",
    },
    {
        "status": "pass",
        "title": "Distress computed for flagged parcels",
        "threshold": "every flagged parcel",
        "measured": "24,497 tax-delinquent, 959 Treasurer's-sale, 149 L&I-violation parcels, "
        "12,464 city-owned — all scored",
    },
    {
        "status": "pass",
        "title": "Every checklist row live or explicit no-source",
        "threshold": "all rows",
        "measured": "zoning, liens/taxes, L&I, ownership, valuation, deal live; flood, access, "
        "overlays render 'not yet loaded for Pittsburgh' (honest pending)",
    },
    {
        "status": "pass",
        "title": "25-parcel golden set",
        "threshold": "delivered",
        "measured": "docs/wave1-pgh-25parcel-packet.md (all 24 authored districts)",
        "qualifier": "reviewer sign-off pending",
    },
)

_WLM_PARITY: tuple[dict[str, Any], ...] = (
    {
        "status": "pass",
        "title": "Parcels with spine + geometry",
        "threshold": "≥ 98%",
        "measured": "26,197 parcels loaded from FirstMap DE_StateParcels (PIN LIKE '26%', "
        "EPSG:2235); 99.0% carry geometry.",
        "evidence": "Coverage measured on a full ingest of live upstream, 2026-07-28; all 11 wlm "
        "datasets returned success. Prod serves non-empty Wilmington parcel tiles, confirming the "
        "prod load.",
    },
    {
        "status": "pass",
        "title": "Verdict coverage",
        "threshold": "≥ 95%",
        "measured": "100% — 26,197 of 26,197 wlm parcels carry a v8 verdict.",
    },
    {
        "status": "pass",
        "title": "Owner + assessment coverage",
        "threshold": "≥ 95%",
        "measured": "Owner 99.6% / assessed value 99.4% across 26,197 parcels (DE public record, "
        "no Daniel's Law) — a parity win vs hbg/pgh; owner_key auto-computed.",
    },
    {
        "status": "pass",
        "qualifier": "provisional standards; Municode reconfirm pending",
        "title": "Zoning district + by-right buildability",
        "threshold": "resolved + standards live",
        "measured": "base_zoning_code resolved for 99.6% of parcels from the City GIS ZONECODE "
        "(26-hundred prefix normalized); 24 Ch.48 districts seeded as wlm-provisional-2026; "
        "buildability resolves R-3 end to end (test-proven).",
        "evidence": "wlm reads the parcel ZONECODE attribute rather than the ADR-0056 centroid "
        "path — zoning_district holds no wlm polygons and resolved_zoning_source is unset. "
        "Standards remain provisional until the Municode reconfirm is recorded.",
        "owner": "operator",
    },
    {
        "status": "pass",
        "title": "Usable comp / AVM",
        "threshold": "≥ 60% or honest degradation",
        "measured": "88.3% — 23,138 of 26,197 parcels carry a priced last sale, including 1,979 "
        "of 2,403 vacant parcels.",
        "evidence": "Two-digit SALEYR pivot now resolves against the current year, so no wlm sale "
        "dates into the future; seven such rows were corrected on load.",
    },
    {
        "status": "honest_degradation",
        "title": "Distress signals (reduced-stack pilot)",
        "threshold": "computed for flagged parcels or honest degradation",
        "measured": "Structural: DE publishes no open code-violation or vacancy feed. Sheriff "
        "sales are live via CivilView (countyId=24) — every one of the 12 Wilmington rows "
        "reconciled. Vacancy derived from improvement value (2,403 parcels). Reduced stack per "
        "ADR-0064.",
        "evidence": "CivilView serves all of New Castle County: of 56 rows, 12 are Wilmington "
        "(hundred 26) and all 12 matched a loaded parcel; 35 are other NCC towns and are filtered "
        "by market scope; 9 carry no parcel id, of which only 3 are Wilmington and all 3 are condo "
        "units, not land.",
    },
    {
        "status": "blocked",
        "title": "25-parcel golden packet + reviewer sign-off",
        "threshold": "delivered",
        "measured": "Blocker: packet authoring + reviewer sign-off.",
        "owner": "operator",
    },
)

_GATES: dict[tuple[str, str, str], tuple[dict[str, Any], ...]] = {
    ("hbg", GRADUATION, "2026-07-11"): _HBG_GRADUATION,
    ("hbg", PARITY, "2026-07-05"): _HBG_PARITY,
    ("pgh", PARITY, "2026-07-07"): _PGH_PARITY,
    ("wlm", PARITY, "2026-07-28"): _WLM_PARITY,
}


def _satisfied(gate_type: str, status: str, qualifier: str | None) -> bool:
    if gate_type == GRADUATION:
        return status == "met" and qualifier is None
    return status in _SATISFIED_PARITY


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (market_code, gate_type, as_of), items in _GATES.items():
        spec_ref = "§6.4" if gate_type == PARITY else None
        for ordinal, item in enumerate(items, start=1):
            status = item["status"]
            qualifier = item.get("qualifier")
            rows.append(
                {
                    "market_code": market_code,
                    "gate_type": gate_type,
                    "ordinal": ordinal,
                    "title": item["title"],
                    "status": status,
                    "satisfied": _satisfied(gate_type, status, qualifier),
                    "qualifier": qualifier,
                    "threshold": item.get("threshold"),
                    "measured": item.get("measured"),
                    "owner": item.get("owner"),
                    "evidence": item.get("evidence"),
                    "spec_ref": spec_ref,
                    "as_of": date.fromisoformat(as_of),
                }
            )
    return rows


async def seed_market_gates(session: AsyncSession) -> int:
    known = set((await session.execute(select(Market.code))).scalars())
    rows = [row for row in _rows() if row["market_code"] in known]
    for row in rows:
        statement = insert(MarketGateItem).values(**row)
        update_cols = {key: statement.excluded[key] for key in row if key != "id"}
        statement = statement.on_conflict_do_update(
            index_elements=["market_code", "gate_type", "ordinal"], set_=update_cols
        )
        await session.execute(statement)
    return len(rows)
