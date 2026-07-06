# Harrisburg zoning review — instructions (≈20 min per 5 parcels)

Thank you for spot-checking LotScope's Harrisburg zoning read. This validates the pilot before we lift its "provisional" label.

## What the tool claims (and doesn't)
- For each parcel we resolve a **zoning district** spatially (parcel centroid inside a district polygon) and read the **dimensional standards** (min lot size, height, setbacks, coverage) verbatim from **Title 7 §7-307.3A** of the city code.
- **"Provisional" means** we have not yet had a local expert confirm the district assignments and dimensional read against the city's own zoning map. That's what this review is.
- **Known-thin by design (not bugs):** (1) **by-right *use*** is not yet shown — the §7-305.7 use table is a separate attachment we haven't loaded, so we verify *district + dimensions* only for now; (2) **comps are absent** — Dauphin publishes no sale prices, so value estimates are honestly low-confidence; (3) **code-enforcement/violations** are absent — the city publishes no such dataset. None of these are errors; they're the honest state of the sources.

## How to review (packet: `wave0-hbg-25parcel-packet.md`)
For each of the 25 rows:
1. Look the parcel up on the **City of Harrisburg zoning map / viewer** (or the official zoning map) by address or parcel number.
2. Fill **City map district** = the district the city's map shows.
3. Fill **Agree?** = **Y** if it matches "Our district", **N** if not.
4. In **Notes**, record *why* if you disagree — especially: wrong district near a boundary (our geometry is the TCRP generalized layer), and anything odd in the **RF / Riverfront** rows (its setbacks are location-conditional and left blank on purpose).

## Returning it
Send the filled-in file back. If agreement is high (≈23/25+), we lift the provisional cap and recompute Harrisburg at a confirmed version. Any disagreements point us at either a district-geometry fix or a standards correction — both actionable.
