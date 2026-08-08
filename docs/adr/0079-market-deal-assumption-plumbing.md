# ADR-0079 — Market deal assumptions reach the computation, and there is one key convention

Status: accepted (2026-08-08)

Amends the deal engine's assumption handling. Records a defect fix, not a methodology change.

## Context

`market.deal_assumption_overrides` existed, was seeded, and was displayed — and never reached a single computed number.

Two independent faults held it apart from the math:

1. **No computation path applied it.** `_assumptions()` took request values and fell through to platform settings. The market column was read in exactly two places: once in `analyze_parcel_deal` to derive the `assumptions_source` *label* (fetched after the assumptions were already built), and once in `build_underwriting` to populate the *display* inventory. Neither fed the resolver. Every stored verdict, every scenario set and every underwriting case therefore computed at platform defaults regardless of market.
2. **The key names did not match.** The seed wrote settings-style `deal_construction_cost_per_sqft`; `build_assumption_set` read assumption-style `construction_cost_per_sqft`. Two test files asserted the two conventions separately and both passed, because nothing crossed the seam.

Harrisburg is the only market carrying an override — 145.0 against a platform 175.0.

## Decision

**One resolution, two consumers.** A single resolver fetches the market's overrides, discards keys outside the canonical set (logged, never silently applied), and feeds both the computed `DealAssumptions` and the displayed assumption inventory. Displayed provenance and computed numbers can no longer diverge, because they are the same dictionary.

**Precedence is uniform everywhere:** request parameter or user profile → market override → platform settings. In underwriting the user profile occupies the request slot.

**Canonical key names are the unprefixed assumption-style forms** — `construction_cost_per_sqft`, `soft_cost_pct`, `selling_cost_pct`, `target_margin`, `default_unit_sqft`, `max_unit_sqft`. They already matched `build_assumption_set` and the user-profile keys; the settings-prefixed form now lives only in `core/config.py`, where it belongs. A hand-written idempotent migration renames existing rows.

`_assumptions()` gained `default_unit_sqft` and `max_unit_sqft` parameters. The display inventory had always advertised those two as overridable while the resolver could not accept them — the set is now the same on both sides.

The `calibrated` marker stays orthogonal: it flags provenance, is never treated as a value, and is excluded from normalisation.

## Consequences

**No verdict version bump, and no recompute.** The formula, the precedence design and the comp selection are unchanged; an input-plumbing defect was repaired. The version rule exists to prevent silent drift, and the measured drift here is zero:

- Harrisburg holds 19,502 verdicts. **None carries `arv` or `max_allowable_offer`** — all deal fields are null.
- Harrisburg holds 11,738 sales and **none carries a price**, so no ARV can be derived, so no deal exists to change.
- Run through the real service at both 175 and 145, six Harrisburg parcels return `arv=None, mao=None` at both.

So the market whose override was inert is also the market that cannot currently produce a deal. **The fix changes no output anywhere today.** It is repaired now because it is a latent correctness defect that becomes live the moment Harrisburg gains priced sales or any other market gains an override — at which point the wrong numbers would appear without anyone touching the deal engine.

Philadelphia, Pittsburgh and Wilmington seed empty override dictionaries, and an empty dictionary is proven behaviour-neutral by test: `_assumptions(market_overrides={})` equals `_assumptions()`.

Two smaller repairs ride along, both recorded here because they touch what the user is told:

- The sensitivity grid refused to render whenever no buildable area was derived, giving the reason "construction cost cannot be varied". That was false — `analyze_deal` models exactly that case from the default unit size, and the cost multiplier scales the rate regardless. The grid's availability now mirrors what `analyze_deal` can model; the remaining refusal is for a missing development programme and says so.
- Acquisition provenance (`land_value_is_assessed`) was dropped when `build_underwriting` fell back to assessed value, and again wherever the sensitivity and case paths rebuilt their inputs. It is carried through now. It was invisible because those paths discard reasons, which is a reason to fix it quietly rather than a reason to leave it.
