# ADR-0065 — Field-state trust contract and source provenance

Status: proposed (2026-07-28)

Amends the verdict contract established by ADR-0003 and ADR-0007. Required by `docs/PRD-amendment-03-launch-readiness.md` §8.1–8.3 (Slice LR-2). Backlog tickets LR-B-001, LR-B-003, LR-B-005.

## Context

Amendment 03 §6.2 requires the product to say so when it does not know, and §8.1 requires every material output to expose one of four states: Verified, Calculated, Estimated, Unavailable. §8.3 requires source age near the result it qualifies. Neither exists today.

What exists is real but insufficient:

- **`verdict.sources`** is `list[dict[str, Any]]`, shaped `[{dimension, sources: [...]}]` and merged in `verdict/composition.py:61`. It is **dimension-level, not field-level**, and **untyped** — each domain invents its own keys. `zoning/service.py:218,247,363` emits `{source, method}`, `{source, code, version}`, `{source, field}`; `valuation/service.py:167` emits `{source, comp_count, radius_ft, years, use_class, package_deeds_excluded}`; `risk/service.py:229` emits eight bare `{source}` entries; `deal/service.py:182` emits `{dimension, arv_comps, radius_ft, years, use_class}`.
- **`markets/capabilities.py`** distinguishes `no_data_source`, `pending_load`, and `available` **per market and category** — an honest-degradation system that is the closest existing analogue to the taxonomy, and the right thing to build on rather than replace.
- **`checklist/schemas.py`** has its own `ChecklistAvailability` (`available`/`no_data_source`/`pending_load`), a third vocabulary.
- **`dataset_freshness`** records `last_success_at` per `(market_code, dataset)`.

Nothing carries a `status`. Nothing carries an `as_of`. A field that is genuinely unknown is indistinguishable from one that was computed confidently.

### The vocabulary mismatch

Freshness cannot simply be joined onto provenance. Verdict source labels are **internal storage tables**; `dataset_freshness` is keyed by **upstream ingestion dataset**. Measured against the Philadelphia freshness rows:

| Verdict source label | `dataset_freshness.dataset` | Relationship |
|---|---|---|
| `rtt_summary`, `historicdistricts_local`, `zoning_overlays`, `zoning_rco` | identical | 1:1 |
| `pwd_parcel` | `pwd_parcels` | 1:1, name differs |
| `zoning_district` | `zoning_base_districts` | 1:1, name differs |
| `tax_status` | `real_estate_tax_delinquencies` | 1:1, name differs |
| `flood_zone` | `fema_flood` | 1:1, name differs |
| `street_centerline` | `streets` | 1:1, name differs |
| `li_event` | `violations`, `permits`, `demolitions` | **1:many** |
| `parcel` | `opa_properties_public`, `pwd_parcels` | **1:many** |
| `zoning_standard` | *none* | **seeded, never ingested** |

Two labels are one-to-many, and `zoning_standard` has no ingestion dataset at all — it is seeded code with a `code_version`, so its freshness concept is a standards version, not a sync time. Any design that assumes a name-equality join is wrong.

## Decision

### 1. A reusable provenance structure in `core/`, emitted by the domains

`core/provenance.py` defines:

- `FieldState = Literal["verified", "calculated", "estimated", "unavailable"]`
- A frozen `FieldProvenance` carrying `status`, `source_label`, `as_of`, `method_version`, `limitations`, and the origin discriminator required by §8.2.

Each domain service emits provenance **for its own material fields**, alongside its existing result. `verdict` composes; it does not infer. This keeps the boundary rule in CLAUDE.md §10 intact — verdict must not encode zoning's or valuation's notion of what is verified, because that knowledge belongs to those modules and would drift the moment either changes.

Rejected alternatives:

- **Verdict schema only.** Smallest blast radius, but verdict would have to infer each domain's state, encoding other modules' truth. That is precisely the boundary violation §10 forbids, and it would silently rot.
- **Presentation layer only.** No verdict-version bump and no domain churn, but the states would be neither persisted nor reproducible, which contradicts §LR-V001's "versioned and reproducible" and leaves corrections (§8.5) unable to reference the exact computed result they dispute.

### 2. Additive, not a replacement

`verdict.sources` stays exactly as it is. `FieldProvenance` is added alongside. Nothing that reads `sources` today breaks, and the two coexist until consumers migrate. Amendment 03 §LR-2 asks for backward compatibility where practical; here it is practical.

### 3. States are derived, never asserted

- **Verified** requires an identified source policy — a named authoritative or contracted source with a recorded `as_of`. A field may not be labelled Verified merely because a value is present. The execution document states this as a restriction and it is binding.
- **Calculated** requires identified inputs and a `method_version`.
- **Estimated** covers model, comparable, heuristic, and assumption-derived results, and must carry the confidence already produced by `valuation` and `deal`.
- **Unavailable** covers not obtained, not evaluated, stale beyond policy, and insufficient evidence. It is the default when evidence is absent — never a falsy value.

### 4. Existing vocabularies map in, they do not multiply

`markets/capabilities.py` category state is an **input** to field state, not a competitor:

| Capability state | Contributes |
|---|---|
| `no_data_source` | `unavailable`, with the existing market-specific detail as `limitations` |
| `pending_load` | `unavailable`, with the pending detail as `limitations` |
| `available` | the field's own derived state |

`checklist/schemas.py::ChecklistAvailability` is the same three values and will be reconciled to the shared type rather than left as a third vocabulary. `ChecklistStatus` is a separate axis (pass/warn/fail/info) and is untouched here — widening it to the five values §LR-B001 requires belongs to LR-5.

### 5. Freshness resolves through an explicit mapping

A declared `source_label → contributing dataset(s)` mapping lives beside the provenance structure. It handles the renames, the two one-to-many cases, and the `zoning_standard` exception, whose freshness is its `code_version` rather than a sync timestamp. `as_of` resolves to the **oldest** contributing dataset's `last_success_at`, because a composite is only as fresh as its stalest input.

Staleness policy per dataset is owner-set (backlog LR-B-005); until it is set, age is reported without a stale verdict rather than guessed at.

### 6. No persistence in this ADR

Provenance is computed at composition time from data already stored. No new column on `parcel_verdict` and **no migration** for the taxonomy. If a later slice needs historical replay of states as they stood, that is a separate decision with its own ADR.

The correction workflow (§8.5, LR-B-004) **does** require new tables; it is deliberately excluded here and gets its own ADR so a data-model decision is not buried inside a contract decision.

### 7. Verdict version

`VERDICT_VERSION` stays **`v8`**. The change is additive, computed values are unchanged, and no existing field's meaning moves. Goldens across phl/hbg/pgh/wlm must be byte-unchanged for the existing fields; that is the test that proves this claim. Should any computed value shift, this ADR is wrong and the version bumps.

## Consequences

- Four service modules gain provenance emission. Their computation is untouched; this is additive output.
- `verdict` gains composition only, consistent with its role as the composer.
- The frontend can render a per-field state and a source age without asking each panel to invent its own wording — the freshness panel (§8.3) and missing-data presentation (§8.4) become presentation of a contract rather than four bespoke implementations.
- Corrections (LR-B-004) can reference the exact field, its state, and its source age at the moment the user disputed it.
- **Cost:** four modules change in one slice. The alternative — one module at a time — would leave the verdict emitting a partial contract for several slices, which is worse for consumers and for testing.
- **Risk:** "Verified" is the label most likely to be applied too generously. The source-policy requirement and a test asserting no field reports Verified without a source reference are the guards.
- §8.4 remains unproven until the audit in LR-B-003 runs. This ADR gives that audit the vocabulary it needs; it does not substitute for it.

## Open questions for the owner

1. **Staleness policy per dataset** — at what age does each source become Unavailable rather than merely old? Until set, age is shown without a stale verdict.
2. **Source policy for Verified** — which sources count as authoritative? Philadelphia OPA and PWD are the obvious candidates; whether a derived-but-authoritative field such as `resolved_zoning_code` qualifies is a judgement call with real customer consequences.
