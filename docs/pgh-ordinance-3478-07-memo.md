# Allegheny County Ordinance 3478-07 — one-page memo (HANDOFF for legal read)

*For the owner's legal read. The capabilities default (owner surfaces OFF for `pgh`) ships regardless of timing; turning them on is your decision after this read.*

## What 3478-07 prohibits
Allegheny County Ordinance **3478-07** (signed by the Chief Executive, 2007) prohibits **public search of county assessment records by owner name**. In practice the county's published assessment data — including the WPRDC open dataset — **excludes owner name and contact information** to comply.

## What the open-data license permits
The WPRDC Property Assessments dataset is published under an open-data license (record the exact per-dataset license in `docs/data-licenses.md`). It permits use of the fields provided — parcel id, address, characteristics, assessed/fair-market values, sale history, use/class codes. It simply **does not contain owner names**, and the ordinance forbids building an owner-name search index over assessment records.

## The data reality (independent of the legal question)
The WPRDC assessment feed carries **no owner-name field at all** (`OWNERCODE`/`OWNERDESC` are owner-*type* codes — e.g. individual vs corporate — not names). So even setting the ordinance aside, LotScope has **no owner-name data to power** an owner search or owner-portfolio panel for Pittsburgh.

## Product surfaces affected (off for `pgh` by default)
- **Leads — owner dimension** (search/filter/skip-trace by owner): disabled for `pgh`.
- **Owner-portfolio panel** (all parcels by the same owner): disabled for `pgh`.
- Everything else (parcel intelligence, verdict, zoning, distress, comps, inventories) is unaffected — none of it depends on owner name.

## The decision for you
1. **Keep off (default, recommended):** honest — we have no owner data for Pittsburgh and the ordinance is respected. Ship pilot with owner surfaces hidden for `pgh`.
2. **Turn on:** would require (a) a legal read confirming an owner-name source outside the assessment records is permissible under 3478-07 and any RTK constraints, and (b) actually sourcing owner names (recorder deeds? a licensed vendor?) — out of scope for this wave and not from the assessment feed.

**No action blocks the wave** — the pilot ships with owner surfaces off. This memo is here so the "on" decision is yours to make deliberately, not by default.
