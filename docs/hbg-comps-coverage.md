# Harrisburg comps coverage — the honest ceiling (graduation Slice 5)

Per the Slice-0 decision (accept thin comps as the honest ceiling; no paid Recorder Landex bulk), this slice **measures and reports** comp coverage rather than loading new sales. The numbers go into the graduation gate as-is.

## Measured coverage (2026-07-06)

| Metric | Harrisburg | Philadelphia |
|---|---|---|
| Recorded sales loaded | 11,738 | (full RTT) |
| Sales with a usable **price** | **0** | 100% |
| Vacant parcels | 1,664 | — |
| Verdicts with a value estimate | **0** | (full) |
| Comps per estimate (median) | **0** | (populated) |

## Why — and why it's correct behavior
Dauphin County's published transfer records (`DC_ParcelCharacteristic` deed references) carry grantor/grantee and a document reference **but no sale price** — the only priced-sale source is the **Recorder of Deeds Landex bulk export, which is paid** (per the Slice-0 investigation; no public price). We do not buy data without approval, and that approval was explicitly declined in favor of the honest ceiling.

Consequently the AVM has **no priced comparables** for Harrisburg. The engine degrades correctly:
- `comps` returns **0 comparables**, `confidence = low`, and **no fabricated estimate** (`estimate_low/high = null`) — verified on a live parcel.
- The verdict carries no value estimate rather than a made-up one.
- The reviewer instruction sheet already tells reviewers comps are absent **by design of the sources**, not a bug.

## Ceiling for the graduation gate
Harrisburg's valuation ceiling is **honestly lower** than Philadelphia's: we surface buildability, zoning, distress signals, and ownership, but **not a comped land value**, until a priced-sale source is licensed. This is a disclosed limitation, not a gap masquerading as a clean result. Distress/opportunity weights are **not renormalized** to hide the absence — valuation contributes what it honestly can (little), and the ceiling reflects that.

**To raise the ceiling later** (out of scope now): license the Dauphin Recorder Landex bulk export (paid — requires approval) or ingest STEB county sales files if the state ever publishes the raw per-sale data (today it publishes only the aggregate Common Level Ratio).
