# 32. Comp hygiene: related-party sale exclusion

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 feature **A10**. Extends ADR-0007-era valuation and the AVM (`valuation/`).

## Context

`find_comps` (`valuation/service.py`) selects recorded RTT sales near the subject, filtered by deed presence, `sale_price >= 1000` (`DEFAULT_MIN_PRICE`), a date window, radius, and use-class. That filter still admits **intra-family / related-party transfers** — a deed recorded for nominal or below-market consideration between relatives — which drag the comp-based land estimate down. The AVM already trims price-per-sqft outliers via an IQR fence (`avm.trim_outlier_rates`, `_IQR_FENCE = 1.5`) and reports the excluded count in `reasons`, but a cluster of low family transfers can survive the fence and bias the median.

The `sale` table already carries `grantor` and `grantee` (Text). A cheap, high-signal heuristic is available: a shared surname token between grantor and grantee is a strong related-party indicator.

## Decision

**Exclude comps whose grantor and grantee share a normalized surname token, in `find_comps`, as a pure filter applied before the AVM — and report the excluded count.**

- **Fetch** `grantor` and `grantee` in the comps query (they are already on `sale`); keep the SQL otherwise unchanged (the existing deed/consideration/date/radius/use-class filters stand).
- **Normalize + compare in Python** (pure, unit-testable — not in SQL): uppercase; strip common suffixes (`JR`, `SR`, `II`, `III`, `LLC`, `INC`, `TRUST`, `ESTATE`, etc.); tokenize; a sale is related-party when grantor and grantee **share any token of length ≥ 3**. Token length ≥ 3 avoids matching initials/noise; the suffix strip avoids false hits on entity boilerplate.
- **Order of operations:** related-party exclusion runs first, then the existing IQR trim runs on what remains — so the two are complementary and the impact is incremental (the amendment's "guarded by the existing IQR trim").
- **Transparency:** the excluded related-party count is threaded into the valuation `reasons`, alongside the existing outlier-exclusion note (e.g. "Excluded N likely related-party sale(s) sharing an owner surname.").
- **Property-tested** against known family-transfer fixtures (same-surname grantor/grantee at a low price) and against safe cases (unrelated parties, entity-to-entity, empty/one-sided names) to prove no over-exclusion.

## Consequences

- The AVM median rises toward arm's-length reality where family transfers were previously included; magnitude is bounded because the IQR trim already caught the most extreme cases — this addresses the residual bias, not a wholesale change.
- The heuristic is deliberately conservative and can **over-** or **under-**exclude: hyphenated/maiden-name changes and common surnames (e.g. two unrelated "SMITH" parties) are the known failure modes. Accepted for v1 because (a) the `reasons` line makes every exclusion visible and auditable, and (b) excluding a genuine arm's-length sale only removes one comp from a set, whereas keeping a family transfer skews the median. When uncertain the rule errs toward exclusion only on a shared token ≥ 3 chars, which common-surname collisions will occasionally trip — noted, not solved, in v1.
- No schema change, no new source, no verdict-contract change (the AVM output shape is unchanged; only comp selection and a `reasons` line differ). No `VERDICT_VERSION` bump semantics apply — valuation is recomputed on demand.
- Depends on `grantor`/`grantee` being populated; sales missing either name are treated as **not** related-party (kept), failing safe toward inclusion rather than silently dropping unlabeled sales.
