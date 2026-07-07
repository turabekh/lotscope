# ADR-0057 — Versioned per-market distress scoring profiles

Status: accepted (2026-07-07)

## Context
The motivated-seller distress index (ADR-0015, extended to v2 by ADR-0039) scored every parcel against a single hardcoded set of weights, thresholds, and tier cutoffs living as module constants in `distress/scoring.py`. Those numbers are calibrated for Philadelphia's signal mix (sheriff sale, L&I, Philadelphia tax-delinquency semantics). As the platform took on Harrisburg and Pittsburgh, that single definition became silently miscalibrated for markets whose distress reality arrives through different sources — and there was no record on a scored row of *which* weights produced it.

The recent Harrisburg false-clean tax-delinquency defect was this class of bug: per-market semantics hidden inside market-agnostic code. Golden rule 6 requires a derived datum whose inputs can differ by market to record which input set produced it. Distress had no such provenance.

This is **Slice 1**: make per-market calibration explicit, auditable, and behaviour-neutral. No weight changes here; recalibration is Slice 2.

## Decision
- **Code-resident, versioned profiles.** A frozen `DistressScoringProfile` (`distress/profiles.py`) holds all 17 scoring numbers found in the scorer — 11 weights, the severe-tax dollar/years thresholds, the long-tenure-years threshold, the score cap (previously an unnamed `min(100, …)` literal), and the two tier cutoffs. The registry maps market → profile; `profile_for_market(market)` is the single pure accessor. Git-versioned, not a DB table (mirrors `accounts/tiers.py`).
- **Behaviour-neutral Slice 1.** `philly-distress-v1` encodes the exact live v2 constants. `harrisburg-distress-v1` and `pittsburgh-distress-v1` are byte-identical clones (built via `dataclasses.replace`, differing only in `profile_id`/`market`), enforced by a clone-invariant test. A golden-equivalence test freezes the pre-refactor scorer and asserts identical score/tier/factors across a boundary matrix ($10,000 and 3-year severe edges, the 15.0 tenure edge, cap engagement, tier cutoffs) for all three profiles.
- **All three live markets carry a v1 clone.** The brief scoped Pittsburgh out ("registered at Pittsburgh onboarding"), but pgh is already live with distress-eligible data and the coverage check runs over all parcels; a pgh clone is required to stay behaviour-neutral. Recorded here as a deliberate deviation from the brief.
- **One scorer, explicit resolution.** `score_distress(signals, profile)` — no default profile argument that could mask a missing resolution. The threshold also reaches **signal generation**: `_lead_top_factors` (leads display) reads `long_tenure_years` from the resolved profile, so the same number lives in exactly one place. Market is resolved via `parcel.market_code` in both the live and bulk paths (no prefix-split fallback mixed in).
- **Loud coverage validation.** The distress precompute validates, before scoring, that every distinct `market_code` present has a registered profile; any gap raises `UnknownMarketProfileError` naming the uncovered markets and scores nothing. This is the market-onboarding tripwire.
- **Honest degradation on the live path.** `UnknownMarketProfileError` subclasses `ConfigurationError`, so the per-parcel distress endpoint returns a clean 503 (not an unhandled 500) for an unprofiled market — never a Philadelphia-weighted score.
- **Provenance.** `parcel_distress.profile_id` (nullable; migration `7c3e9f1a2b84`, no backfill — the daily cron converges it) and the live `DistressResult.profile_id`. The leads-list contract is unchanged (profile is per-parcel provenance only).
- **Recalibration deferred.** Authoring genuinely different weights (`harrisburg-distress-v2`, `pittsburgh-distress-v1` proper) is Slice 2 — a data-authoring change released in a coordinated batch. The authority for that batching is `docs/verdict-bump-queue.md`; the batching principle originates in ADR-0028's consequences (verdict-affecting additions ride the next contract change so they recompute together).

### Two orthogonal version axes
`DISTRESS_VERSION` (currently `"v2"`) versions the **scoring logic** — which factors exist and how they combine. `profile_id` versions the **weights** — the numbers fed to that logic. They are independent: changing a weight bumps `profile_id` only; adding a new factor or rule bumps `DISTRESS_VERSION` only. A bump on one axis never implies a bump on the other, and they must not be "aligned." Both are recorded on every scored row (`version` and `profile_id`).

## Harrisburg signal-availability inventory (Slice-2 input)
Per weighted signal, does current Harrisburg data populate it? (from the dev load; reflects the hbg feed-availability state in the ADR-0054 honest-degradation ledger.)

| Signal (weight) | Populates for hbg? | Note |
|---|---|---|
| vacant (10) | ✅ 1,664 | derived vacancy |
| absentee (10) | ✅ | address + mailing present (heuristic quality depends on Dauphin mailing format — Slice-2 review) |
| **long_tenure (5)** | ❌ **structurally dead** | 11,738 DEED-type sales but **0 carry a `sale_date`** (Dauphin is deed-refs-only) → `years_since_last_sale` always NULL |
| **portfolio_distress (10)** | ❌ **structurally dead** | needs ≥5 open L&I violations per owner; hbg has **0 L&I violations** (no code-enforcement feed) |
| sheriff_sale (30) | ❌ not loaded | Dauphin RETSL list is a seasonal PDF; pipeline ready, no live list |
| tax_delinquent / severe (15/15) | ❌ not loaded | Dauphin delinquency not yet loaded (pending) |
| liens (10) | ❌ not loaded | — |
| L&I dangerous/violations (15/5) | ❌ not loaded | no feed |
| demolition (5) | ❌ not loaded | no feed |

**Headline:** the hbg clone carries two weights (`long_tenure`, `portfolio_distress`) that are dead even once the other feeds load — one because Dauphin sales lack dates, one because there is no L&I feed. The rest are dark today for data-availability reasons, not calibration. Slice 2 must decide whether to zero the two dead weights and redistribute, and re-tune the rest once the feeds land.

## §8.3(c) — Market-tuned constants left in place (named, not moved)
The scorer itself is market-agnostic. The market-flavoured numbers that remain in **signal generation** (`distress/service.py`), out of scope this slice: `_ARMS_LENGTH_MIN_PRICE` ($1,000), the tired-landlord thresholds (≥3 parcels / ≥5 open violations), and the `document_type ILIKE '%DEED%'` tenure semantics. These are Philadelphia-flavoured but structural; candidates for a future signal-generation profile, unchanged here.

## Consequences
- **Harrisburg and Pittsburgh remain intentionally Philadelphia-calibrated** until Slice 2 — now *named and visible* (`harrisburg-distress-v1`, `pittsburgh-distress-v1`) rather than implicit.
- **Every future market must register a distress profile before its first distress recompute.** Add this to the market-onboarding checklist next to the market-literal sweep; the coverage tripwire enforces it (the precompute fails loudly otherwise).
- **Slice 2 trigger:** once a market's distress feeds are loaded and the §5.3-style inventory is in hand, author its recalibrated profile and release it in the next coordinated bump per `docs/verdict-bump-queue.md`. It requires per-weight sign-off and does not touch the verdict contract or verdict version.
- Behaviour is unchanged for every parcel in every market today (proven by the golden-equivalence and existing service tests), and every scored row now records its profile.
