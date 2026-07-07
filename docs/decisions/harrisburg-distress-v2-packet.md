# Harrisburg distress recalibration — decision packet (`harrisburg-distress-v2`)

Read-only analysis to support sign-off of `harrisburg-distress-v2` weights on evidence. No code, data, migration, registry, or `profiles.py` change was made producing this; the proposed profile exists only in this packet and a throwaway script (appendix). Slice 2 implementation begins only after the §C6 checklist returns signed.

**Snapshot:** local dev database, 2026-07-07, post-Pittsburgh-ingest (phl 550,939 · hbg 19,502 · pgh 143,355 parcels). Every figure below is from this snapshot. Never queried prod. Profile axes per ADR-0057: `DISTRESS_VERSION` (logic) is untouched; only `profile_id` (weights) is in scope.

**One-line finding:** Harrisburg has essentially two live distress signals — **vacant** and **absentee**. Every source-fed signal (tax, sheriff, liens, L&I, demolition) is dark because the feeds are not loaded, `long_tenure` is structurally dead, and `portfolio_distress` fires only as a cross-market owner-grouping artifact. A genuine recalibration is not possible until Harrisburg's distress feeds load; the defensible v2 today is a **correctness trim** (zero the two unsupported weights), not a re-weighting.

## C1 — Signal ← source mapping and population (hbg; pgh informational)

| Signal (clone wt) | Source / derivation | hbg populated | hbg % | pgh (info) | Classification |
|---|---|---|---:|---:|---|
| sheriff_sale (30) | `tax_status.in_sheriff_sale` (RETSL) | 0 | 0% | 959 | absent — feed not loaded (seasonal RETSL PDF) |
| tax_delinquent (15) | `tax_status.is_delinquent` (Dauphin) | 0 | 0% | 24,497 | absent — feed not loaded |
| severe_delinquency (15) | `total_due ≥ $10k` OR `years_owed ≥ 3` | 0 | 0% | — | absent — depends on tax feed |
| liens (10) | `tax_status.lien_count > 0` | 0 | 0% | — | absent — feed not loaded |
| li_dangerous (15) | `li_event` unsafe/imminently-dangerous | 0 | 0% | — | absent — no L&I feed (no-source per ADR-0054) |
| li_violations (5) | `li_event` violation | 0 | 0% | 149 | absent — no L&I feed |
| demolition (5) | `li_event` demolition | 0 | 0% | — | absent — no L&I feed |
| vacant (10) | derived vacancy (`is_vacant`) | 1,664 | 8.5% | 22,438 | **populated** |
| absentee (10) | situs vs mailing (`is_absentee`) | 11,978 | 61.4% | — | **populated** |
| long_tenure (5) | absentee AND `document_type ILIKE '%DEED%'` sale with a date, ≥ 15 yrs | 0 | 0% | 11,141 | **structurally absent** — Dauphin sales carry deed refs but **no `sale_date`** (0 dated deeds), so tenure is always NULL |
| portfolio_distress (10) | owner_key in the tired-landlord set (≥3 parcels AND ≥5 open violations) | 87 | 0.4% | — | **artifact** — see note |

**Thresholds:** `severe_due=$10,000`, `severe_years=3` — untestable (tax feed absent). `long_tenure_years=15.0` — moot (0 dated deeds).

**portfolio_distress note (material).** hbg has **0** L&I violations, yet 87 hbg parcels score `portfolio_distress`. Cause: `tired_landlord_owner_keys` groups owners **globally across all markets** (not market-scoped). 956 hbg owners hold ≥3 parcels, but the ≥5-violations half of the "tired" test is met only via violations on **non-hbg** parcels sharing the same normalized `owner_key` — genuine multi-market portfolios or owner-name collisions. Either way, **hbg's portfolio_distress is not supported by hbg data.** This is a signal-generation scoping issue (separate from the weight) — flagged as a follow-up in §C5.

## C2 — Per-signal decision table (proposed; you dispose)

| Signal | Clone → | Action | Proposed | Rationale |
|---|---:|---|---:|---|
| sheriff_sale | 30 | **keep** | 30 | inert now, but RETSL feed is loadable; zeroing a pending signal would suppress it once loaded |
| tax_delinquent | 15 | **keep** | 15 | Dauphin delinquency pending; keep for when it lands |
| severe_delinquency | 15 | **keep** | 15 | depends on the tax feed; keep |
| liens | 10 | **keep** | 10 | pending feed; keep |
| li_dangerous | 15 | **keep** | 15 | no L&I feed today, but a loadable signal; keep for parity |
| li_violations | 5 | **keep** | 5 | same |
| demolition | 5 | **keep** | 5 | same |
| vacant | 10 | **keep** | 10 | live, primary hbg signal — no evidence to re-weight |
| absentee | 10 | **keep** | 10 | live — no evidence to re-weight |
| long_tenure | 5 | **zero** | 0 | structurally dead: Dauphin sales carry no dates → never fires. Field stays; value → 0 |
| portfolio_distress | 10 | **zero** | 0 | hbg has no L&I; the 87 firings are cross-market owner artifacts, not hbg distress. Remove until hbg L&I loads AND signal-gen is market-scoped |
| severe_due / severe_years | $10k / 3 | keep | $10k / 3 | untestable without the tax feed |
| long_tenure_years | 15.0 | keep | 15.0 | moot (weight zeroed) |
| tier cutoffs | 60 / 30 | keep | 60 / 30 | see §C3 |
| score_cap | 100 | keep | 100 | harmless |

Net proposed change: **two weights → 0** (`long_tenure`, `portfolio_distress`). Everything else keep. This is a correctness trim, not a re-weighting — there is no hbg distress data to re-weight against yet.

## C3 — Structural consequences

- **Max achievable raw hbg score:** clone = **30** (vacant 10 + absentee 10 + portfolio 10, the 4 top parcels); proposed v2 = **20** (vacant 10 + absentee 10). High (≥60) is unreachable in both; medium (≥30) is reachable in the clone **only via the spurious portfolio signal**, and unreachable under v2.
- **`score_cap = 100` is inert** for hbg (max 20–30) — no action needed, but note it means the score is not comparable to phl/pgh where the cap is real.
- **Tier cutoffs:** under v2 every hbg parcel is **low or none**. This is honest — hbg's distress signal is genuinely weak until feeds load. **Recommend: keep 60/30.** Lowering hbg cutoffs to manufacture "medium/high" from vacant+absentee alone would make an hbg "high" mean something categorically weaker than a phl "high," which is worse than honestly reporting low. Re-tiering is available as a values lever if you want hbg leads ranked into tiers now — say so and I'll model it — but it is not recommended pre-feed-load.

## C4 — Dry-run impact (offline; real `score_distress` + real signal path, proposed v2 threaded in)

Scored **18,597** hbg parcels (excl. city-owned) under the live clone vs. proposed v2.

**Score histogram (clone → v2):**

| Bucket | clone | v2 |
|---|---:|---:|
| 0 | 7,468 | 7,487 |
| 1–10 | 9,443 | 9,488 |
| 11–20 | 1,682 | 1,622 |
| 21–29 | 0 | 0 |
| 30–59 (medium) | **4** | **0** |
| 60+ (high) | 0 | 0 |

**Tier migration matrix (clone → v2):**

| from → to | count |
|---|---:|
| none → none | 7,468 |
| low → low | 11,106 |
| low → none | 19 |
| medium → low | 4 |

**Movers:** 87 parcels change score (all lose `long_tenure`=0 or `portfolio_distress`=0 weight; every mover's factor *list* is unchanged — only the summed weight drops). Representative: `hbg:01-011-046` 30→20 (vacant+absentee+portfolio), `hbg:01-005-001` 20→10, `hbg:01-006-010` 10→0. The 23 tier-changers (19 low→none, 4 medium→low) are exactly the parcels whose only score came from the two removed weights.

**Leads preview:** hbg has **0** rows in `parcel_distress` today (the distress precompute has only ever run for phl), so there is no current hbg leads list to reorder. Simulated top leads under both profiles are dominated by vacant+absentee parcels (score 20); under the clone, 4 parcels edge above them at 30 via the cross-market portfolio artifact — v2 removes exactly that artifact from the top of the list. Net: v2 makes the ranked list *more* honest, not less.

## C5 — Release-path recommendation

**(a) Independent Harrisburg-only distress recompute** — legitimate: distress is its own versioning axis (ADR-0057), market-scoped, outside the verdict contract. Cost is small: ~19,502 hbg parcels; the distress recompute is signal-SQL + arithmetic (no zoning/comp/geometry), well under the verdict batch's weight — estimate low single-digit minutes. **Caveat:** `recompute_all_distress` currently has **no market filter** (unlike the verdict job's `--market`); an hbg-only run needs a one-line market predicate added to the job, or a full all-market recompute (713k parcels, still cheap for distress). The change touches only 87 hbg rows regardless.

**(b) Batch with the v9 verdict queue** (`docs/verdict-bump-queue.md`) — release-discipline consistency, but couples a trivial Harrisburg-only correctness trim to the much larger, separately-gated verdict bump and delays it.

**Recommendation: (a), scoped small.** The v2 change is a correctness trim on one pilot market, not a verdict-affecting change; the queue exists for verdict-contract coupling, which this does not have. Ship it independently with a market-filtered recompute — *if* you decide to ship at all. **The stronger recommendation is to weigh whether v2 is worth shipping now:** it removes a dead weight and a cross-market artifact (a real if small correctness gain), but it does **not** recalibrate anything, because hbg has no distress data to calibrate against. A meaningful `harrisburg-distress-v2` should wait until the tax / L&I / sheriff feeds load; today's defensible v2 is only the trim.

**Separate follow-up (not Slice 2):** the cross-market `tired_landlord_owner_keys` scoping affects any non-phl market whose owners collide with phl tired owners — worth market-scoping the tired-owner query independent of this weight decision.

## C6 — Sign-off checklist

Fill in; Slice 2 begins only when this returns.

Weights:
- [ ] sheriff_sale → keep 30
- [ ] tax_delinquent → keep 15
- [ ] severe_delinquency → keep 15
- [ ] liens → keep 10
- [ ] li_dangerous → keep 15
- [ ] li_violations → keep 5
- [ ] demolition → keep 5
- [ ] vacant → keep 10
- [ ] absentee → keep 10
- [ ] long_tenure → **zero (0)**
- [ ] portfolio_distress → **zero (0)**

Thresholds & cutoffs:
- [ ] severe_due $10,000 / severe_years 3 → keep
- [ ] long_tenure_years 15.0 → keep (moot)
- [ ] tier cutoffs 60 / 30 → keep (vs. re-tier — circle one)
- [ ] score_cap 100 → keep

Release:
- [ ] Path (a) independent hbg-only recompute  /  (b) batch with v9 — circle one
- [ ] Ship v2 now (trim only)  /  defer until hbg distress feeds load — circle one
- [ ] (ack) separate follow-up: market-scope `tired_landlord_owner_keys`

## Appendix — analysis provenance

Throwaway script (uncommitted, scratchpad): `hbg_distress_dryrun.py`. Invocation from `backend/`:
`uv run python <scratchpad>/hbg_distress_dryrun.py`
It reads the local snapshot only, builds `harrisburg-distress-v2` in-process via `dataclasses.replace(HARRISBURG_DISTRESS_V1, long_tenure_weight=0, portfolio_distress_weight=0)`, and scores every hbg parcel through the real `score_distress` and `_BULK_SIGNALS_SQL`/`_signals` path. No writes. Population figures are direct `psql` counts against the snapshot.
