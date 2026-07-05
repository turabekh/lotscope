# 50. ZBA variance outlook signal

Date: 2026-07-05

## Status

Accepted

## Context

When a verdict says "variance likely" — correct for an undersized lot such as 940 sqft in RSA-5 (min 1,440) — it reads as a red flag. But the investor's real question is empirical: *how often does the Philadelphia ZBA actually grant these?* Practitioners report dimensional variances on rowhouse infill are granted routinely. OpenDataPhilly publishes L&I/ZBA appeals with decisions on the same Carto SQL API used elsewhere, so we can compute a real grant rate and turn a red flag into a priced risk. The README already promises "variance likelihood"; ADR-0006 lists undersized-lot nuance as unencoded.

Verified against the live `appeals` table: ZBA appeals span **two** `applicationtype` labels (`RB_ZBA` and `Zoning Board of Adjustment`); decisions include `GRANTED`, `GRANTED/PROV`, `DENIED`, `DENIED/PROV`, plus non-decisive outcomes (`WITHDRAWN`, `DISMISSED`, `CONTINUED`, `HELD`, …). There is **no** refusal-type / dimensional-variance field (`appealtype` is null), so the population cannot be narrowed to dimensional variances.

## Decision

Surface an empirical ZBA grant rate as a **standalone per-parcel signal** (the ADR-0028 pattern) — no verdict-contract change in this slice.

- **Population:** decided ZBA appeals (`GRANTED`/`GRANTED/PROV`/`DENIED`/`DENIED/PROV`) in the trailing 36 months, on parcels sharing the subject's `base_zoning_code`. The district join happens at query time via `parcel`; unresolved appeals (null parcel key) are excluded from the count.
- **Metric:** `grant_rate = (GRANTED + GRANTED/PROV) / decided`. Non-decisive outcomes are excluded from the denominator. Proviso grants count as grants; proviso denials count as denials.
- **Local rate:** if ≥30 decided appeals also exist within the subject's ZIP, a secondary local rate is returned alongside the district rate.
- **Honest degradation:** fewer than 10 decided samples returns a null rate with a reason. Because refusal-type granularity is unavailable upstream, the population is labelled "all ZBA appeals for {district} parcels", never "dimensional variances".
- **Surface:** `GET /parcels/{id}/variance-outlook` (auth), plus a line inside the Buildability card shown only when `needs_variance` is true. The RCO meeting requirement is already a risk flag on the panel and is not duplicated here.
- **Privacy:** appellant names (`opa_owner`, `primaryappellant`) are not ingested and never surfaced.

## Consequences

- Investors see a priced grant rate instead of a bare "variance likely", grounded in recorded outcomes and clearly labelled informational.
- The signal is deterministic and testable: SQL fetches decision counts; a pure function computes the rate.
- **Deferred:** folding a variance-outlook signal into the verdict contract (score/flag) waits for the next batched `VERDICT_VERSION` bump, so this slice does not trigger a recompute.
- **Known limitation:** without upstream refusal-type data, the rate covers all ZBA appeals for the district, not dimensional variances specifically; the label says so. Narrowing would require parsing `appealgrounds` free text, deferred.
