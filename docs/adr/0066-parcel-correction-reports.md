# ADR-0066 — Parcel correction reports

Status: accepted (2026-07-28)

Required by `docs/PRD-amendment-03-launch-readiness.md` §8.5 and §6.7 (Slice LR-2). Backlog ticket LR-B-004. Depends on ADR-0065.

## Context

There is no way for a user to tell us the product is wrong about a parcel. Amendment 03 §22 lists "no correction route" as a P0 blocker for a paid beta, and §6.7 requires corrections to become product intelligence rather than support noise.

The reason this is P0 rather than a nicety: when LotScope is wrong about a real Philadelphia parcel — a district, a unit conclusion, a missed master-plan requirement — the customer discovers it during their own diligence and we never learn. The gold set (LR-Q001) catches errors we thought to look for. Corrections catch the ones we did not.

ADR-0065 now gives every material field a state, a source, and an age. That is what makes a correction actionable: without it a report says "the zoning is wrong", with it a report says "this field claimed *calculated* from `zoning_district` as of a given date, and it is wrong."

## Decision

### 1. A `corrections` domain module

New `backend/src/lotscope/corrections/` with the usual `models.py`, `schemas.py`, `service.py`, `tests/`. It owns the record and its triage lifecycle. `api` stays thin.

Corrections do not belong in `parcels` or `verdict`: they are user-submitted assertions *about* those modules' output, and folding them in would put a support workflow inside a computation module.

### 2. The record snapshots, it does not join

Every required §8.5 element is stored **as it stood when the user reported it**:

| Captured | Why snapshot rather than join |
|---|---|
| user id, parcel number, market | — |
| section and optional field name | The field key from the ADR-0065 contract when the user disputes one figure |
| verdict version, verdict computed-at | The verdict will be recomputed; the disputed one must remain identifiable |
| field state, source label, source as-of | ADR-0065 states are recomputed too; the disputed state must survive |
| user description | — |
| optional attachment reference | — |
| triage status, resolution, resolved-at, resolver | — |

A join would report today's state for yesterday's complaint, which makes triage impossible and would quietly rewrite the evidence. The cost is duplication; the alternative is losing the only record of what the user actually saw.

### 3. Triage lifecycle

`open → triaged → resolved | rejected`, with `resolved_at` and the resolving user recorded on exit. `rejected` is a first-class outcome: some reports will be the product being right and the user mistaken, and pretending otherwise inflates the §20.3 trust metrics we intend to steer by.

Transitions are enforced in the service. A resolution requires a note — an unexplained "resolved" teaches nobody anything.

### 4. Attachments are references, not files

The record stores an optional attachment **reference** string. No upload, no storage, no signed URLs in this slice.

Amendment 03 §8.5 asks for "attachment or screenshot reference", and building an upload path drags in object storage, virus scanning, and a retention story that would dominate the slice. When a paid beta shows attachments are needed, that is its own decision.

### 5. Privacy and retention

- Correction text is **user-authored free text about a specific property** and must be treated as potentially containing owner PII, contact details, or commercial intent. It is restricted to the reporting user and admins, never rendered on public surfaces, and never logged.
- **Corrections must never be sent to analytics.** The execution document states this as a binding restriction for LR-2, and ADR-0065's analytics work (LR-B-018) must exclude this table by construction rather than by convention.
- Retention follows CLAUDE.md §13 minimisation. Resolved corrections are kept because they are the trust record; a deletion policy is an owner decision recorded when one is set.

### 6. Abuse and volume

Submission is authenticated and rate-limited through the existing tier machinery rather than a new mechanism. §20.3 measures corrections per 100 verdict views, so the rate is a signal worth keeping honest — throttling should shape abuse, not suppress genuine reports.

### 7. Migration

One additive table. No change to `parcel_verdict`, `parcel`, or any existing contract. Nothing recomputes.

## Consequences

- The last P0 blocker in LR-2 closes, and §17.3's per-deal feedback record (LR-B-036) gains a real substrate.
- Triage is operator work. A correction route with no one reading it is worse than none, because it implies a promise. LR-B-029 (support ownership) is the paired commitment and is owner action.
- Snapshotting means a correction can be reconciled against a later verdict to show whether the fix landed — the basis for the §20.3 trust metrics.
- **Risk:** the volume is unknown. If it is high, triage capacity becomes the constraint before code does. That is a beta finding, not something to pre-engineer.
