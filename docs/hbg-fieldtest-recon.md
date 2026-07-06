# Harrisburg field-test recon (hbg:02-021-052, 301 S 14th St)

Slice-0 diagnostics for the field-test batch. No behavior change. Findings, reader-source table, bump-queue draft, plan.

## Ground truth for the parcel
- `parcel.base_zoning_code` = **NULL** (Dauphin's extract carries no per-parcel zoning attribute; OPA always fills it for phl). Spatial resolution succeeds → **RM**.
- `lot_area_sqft` = **2484.04** (polygon `ST_Area(geom_local)`); county record 2,295.
- `land_value`/`market_value` = **2300** (base-year); `assessment_year` NULL.
- Live composed verdict: **"RM: buildability uncertain; no major risk flags"**, `can_build_by_right=False`, **`needs_variance=None`**, `conforms=None`.

## Bug-1 (zoning split) — READER-SIDE, not a scorer defect → Slice 1 proceeds
The decision point resolves cleanly to reader-side:
- Scorer is correct: `buildability.py:203` sets `needs_variance = (not conforming) if conforming is not None else None` → **None on unknown conformance**.
- Composition is correct: `composition.py:89-94` yields **"buildability uncertain"** when `needs_variance` is falsy — *not* "variance likely". The field-test's "variance likely" was a prior/loose state (likely AI narration); current summary says "buildability uncertain".
- The split is that **display surfaces read the NULL `base_zoning_code` attribute** while verdict surfaces read the resolved district.

**Reader-source table**

| Surface | Location | Reads | hbg renders | Fix (Slice 1) |
|---|---|---|---|---|
| Snapshot facts (→LLM) | `ai/service.py:75,116` | `base_zoning_code` | "zoning unknown" | feed resolved district |
| Parcel chip / dossier | `ParcelDossier.vue:278` | `base_zoning_code ?? 'No zoning'` | "No zoning" | resolved district (+ method tooltip) |
| Compare / Assemblage / OwnerPortfolio / SavedLots | those .vue | `base_zoning_code` | "No zoning"/"—" | resolved district |
| Map overlay | `MapView.vue:165,369` | tile `base_zoning_code` | letter/popup "—" | tile carries resolved district (verify) |
| Verdict summary | `composition.py:91` | `needs_variance`→resolved | "RM: buildability uncertain" | ✅ correct |
| VerdictHero hint | `VerdictHero.vue:40` | `needs_variance` | ✅ correct | ("Title 14" literal is a minor market-leak) |
| Checklist zoning item | verdict conformance | verdict | "conformance could not be determined" | keep verdict-keyed; ensure consistency |
| Variance/ZBA line | `VerdictPanel.vue:112` (`VarianceOutlookLine`) | `/variance-outlook` | **LEAK — renders "Zoning district is unknown"** | gate for hbg |

## Bug-2 (tax truth + risk coverage) — confirmed
- **Liens & taxes** checklist renders **"pass" / clean on ZERO tax-claim rows** for hbg — verified-clean on an unloaded feed. Fix via the existing `checklist_category_state` machinery: add `liens_taxes` → pending/seasonal for hbg.
- **Risk pillar** ("no major risk flags") carries **no coverage qualifier** in a market with absent feeds.
- **ZBA/variance line is a `hidden_surfaces` LEAK, not an intentional degrade:** `zba_variance` is hidden for hbg in the *nav* (AppSidebar filters by `isHidden`), but `VarianceOutlookLine` renders unconditionally inside `VerdictPanel` — so it leaks into the hbg card. Slice 1 gates it by `market.isHidden('zba_variance')`.

## Lot-area audit (Slice 4)
- hbg mapping: `hbg.py:122` → `lot_area_sqft = ST_Area(geom_local)` (polygon). phl: OPA deeded area.
- **`DC_Parcels` carries an `acres` field** (+ `LOT`, `Shape__Area`) → Slice 4 prefers `acres × 43560` (deeded/stated), polygon fallback, `lot_area_source` provenance. The extract value for 02-021-052 is confirmed in Slice 4 against the county's 2,295.

## Common level ratio (Slice 5)
- **Dauphin County 2024 CLR = 40.42%**, effective **Jul 1 2025 – Jun 30 2026** (PA Bulletin 55-27; STEB — "appeals only, not to create value"). phl = 1.0.
- Implied market value = assessed ÷ 0.4042 (e.g. $2,300 → ≈ $5,690). Slice 5 gates "vs. assessment" math on this.

## Bump-queue draft (`docs/verdict-bump-queue.md`)
- **Condemned/Demolished → risk scoring** (Slice 3 ships them as *unscored facts*; feeding them into `risk_score` is a verdict-output change). Precedent: additive risk/scoring changes each took an ADR + version bump (ADR-0015 distress, 0027 access flag, 0039 distress v2).
- **Bug-1: nothing** — the scorer is correct; no methodology change.

## Plan
| Slice | Branch | Touches | Migration? | Risk |
|---|---|---|---|---|
| 1 resolved-district unification | `fix/hbg-resolved-district` | ai/service facts, ParcelDossier + compare/portfolio/saved, VarianceOutlookLine gating | no | phl attribute-path regression |
| 2 tax truth + risk coverage | `fix/hbg-tax-truth` | capabilities (liens_taxes state), risk display qualifier, ai/prompts rules | no | phl clean-state byte-identity |
| 3 repository live | `feat/hbg-repository` | CSV loader, PDF refresh job, hbg_city_status fact, badge + Tax-sales tab | maybe (status col) | key-shape handling; prod-only fetch |
| 4 lot-area source | `fix/hbg-lot-area` | hbg loader (acres pref + provenance), recompute | maybe (provenance col) | conformance flips |
| 5 assessment ratio | `feat/market-assessment-ratio` | migration market.assessment_ratio, gating vs-assessment math | **yes** | phl 1.0 identity |
