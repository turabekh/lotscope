# ADR-0054 — Wave 0: Harrisburg city pilot kickoff

Status: Proposed (2026-07-05)

## Context

Phase P made the platform market-capable (ADR-0051 canonical `{market}:{local_key}` key, ADR-0052 `geom_local` multi-CRS + market-predicate audit, ADR-0053 ingestion transports + market registry, plus B4 `KeyNormalizer` and B10 market-scoped reads). Wave 0 proves that machinery on a real second market before any wave with harder economics. It is a **pilot**: no marketing, one motivated local reviewer for the golden set. Success = the data-parity gate (PRD §6.4) passes and a Harrisburg dossier is as honest as a Philadelphia one, including about what it does not know.

Slice-0 recon inspected the live upstream (Dauphin County ArcGIS Hub, `services2.arcgis.com/EEtiX55QzkHKYQKY`; field mapping in `docs/data-sources-hbg.md`). Findings that shape this ADR:

- The Dauphin assessment tables and parcel geometry are **live-queryable ArcGIS FeatureServers**, not extract-only as the PRD assumed.
- Parcel geometry (`DC_Parcels`) is **EPSG:2272** — this wave does zero CRS work by construction.
- Parcel key is `property_id` = `MM-BBB-PPP` (e.g. `04-038-028`); city membership is `MUNICIPALI = 'CITY OF HARRISBURG'` (~19,827 parcels), not derivable from the key prefix.
- **No sale price or date exists in Dauphin open data** — only `document_number` (deed reference). Comps degrade to near-empty by construction.
- No open code-enforcement feed; no historic/ward layers in the county Hub.
- Official zoning text is on **eCode360** (Title 7); distress is **RETSL** (Tax Claim Bureau upset/judicial/repository), the first non-MCTLA mapping.

## Decisions

1. **Scope: City of Harrisburg only.** Ingest `MUNICIPALI = 'CITY OF HARRISBURG'`. **Defer the `data_only` county fringe** — smaller blast radius for the pilot; revisit after the parity gate. The `parcel.coverage` column ships now (default/backfill `full`) so the fringe is a data decision later, not a migration.

2. **`local_srid = 2272`.** Confirmed from `DC_Parcels` (wkid 102729 / latest 2272). Zero CRS work; loaders assert SRID rather than transform.

3. **Key format & normalizer.** Canonical `hbg:<property_id>`; `HbgKeyNormalizer` preserves the hyphenated `MM-BBB-PPP` form. Golden-file tests built from real extract samples (Slice 1); condo/unit suffix behavior verified against live data before locking.

4. **Transports (corrects PRD Appendix A).** `ArcGisClient` for spine/tax/characteristics/geometry/streets/municipal/land-use/county-zoning (all live FeatureServers). `ExtractClient` / PDF-parse burns in on the **Tax Claim Bureau sale lists** (PDF) — the genuine periodic-extract surface. Per-market `market.source_config` rows carry the service URLs.

5. **RETSL distress mapping (first ADR-0034 non-MCTLA entry).** `in_sheriff_sale` generalizes to `in_forced_sale_pipeline`; scorers unchanged.

   | Source list | Signal | Flag label (detail names the stage) | Distress weight |
   |---|---|---|---|
   | Upset sale | `in_forced_sale_pipeline` | "Tax upset sale (RETSL)" | sheriff-sale weight |
   | Judicial sale | `in_forced_sale_pipeline` | "Tax judicial sale (RETSL)" | sheriff-sale weight (later stage) |
   | Repository | public-inventory status | "Repository — available for purchase ($2,000 min bid)" | **0** (acquirability channel, not distress) |

6. **Recorder posture.** Dauphin Recorder of Deeds; `document_number` is the deed reference; `recorder_url_template` is an index deep-link. No bulk price data — comps run on deed references without prices → low/no confidence.

7. **Deal-assumption overrides (placeholders, to calibrate with the reviewer/partners).** `market.deal_assumption_overrides` for hbg: construction cost markedly below Philadelphia's $175/sqft — placeholder **$145/sqft**; soft/selling/margin inherit Settings. Not authority; per-request overridable as today.

8. **Feature availability (market-capabilities config, not scattered conditionals).**
   - Violations / code-enforcement: **absent** → "L&I & demolition" checklist category = *no data source for this market*.
   - Forced-sale surface: RETSL naming; the Philadelphia sheriff-sales page is relabeled/hidden for hbg.
   - ZBA variance outlook, zoning overlays, RCO: Philadelphia-only → hidden for hbg.
   - Comps/value: honest low/no confidence (no priced sales).
   - Historic / named-area: absent or degrade-with-reason.

9. **No weight renormalization.** Absent signals contribute **zero**; the distress/risk ceiling is honestly lower for Harrisburg. Scorer weights are not rescaled to compensate. This is a deliberate honesty decision — a Harrisburg score is not inflated to look like a Philadelphia score.

10. **`VERDICT_VERSION` stays v8.** Harrisburg verdicts are new rows computed at v8; no contract change this wave. Philadelphia golden-parcel verdicts are asserted unchanged in every slice touching shared code paths.

11. **Corpus gate is absolute.** No Harrisburg zoning logic or `zoning_standard` row is written except from verbatim eCode360 Title 7 text loaded into the corpus. If compliant automated acquisition of that text is not possible, Slice 4 STOPS and hands the acquisition task to the owner.

## Consequences

- The pilot burns in `ExtractClient`/PDF-parse (on distress lists, not the spine), `HbgKeyNormalizer`, the B5 authoring playbook on a short code, the first RETSL mapping, B6 derived vacancy, and the market-capabilities pattern — as intended, at low blast radius.
- Harrisburg dossiers will visibly know less than Philadelphia's (no comps prices, no violations, provisional zoning). That transparency is the pilot's product test.
- License ledger: `docs/data-licenses.md` gains Dauphin ArcGIS Hub (as-is), eCode360/General Code (terms to verify — Slice 4 gate), Dauphin Tax Claim PDFs, PA DCED flood.
- Reversible: hbg is additive; Philadelphia is untouched (asserted per slice). Rolling back a slice is a normal migration/`git revert`.

## Open items resolved in later slices

- eCode360 acquisition-terms verification (Slice 4, corpus gate).
- Harrisburg official zoning district geometry source vs. TCRP generalized (Slice 4).
- Historic-district and ward/neighborhood layer existence (Slice 5; degrade if absent).
- `property_id` condo/unit suffix behavior (Slice 1 golden-file tests).
