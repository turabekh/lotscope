# Wave 2 candidates — Camden, NJ & Wilmington, DE — data-source recon

Feasibility recon for the first two **non-PA** markets. Neither reuses the PA data stack
(OPA/PWD/RTT via Carto); each is a distinct state ecosystem. Endpoints marked **HIT** were
queried live during recon. Verdicts are per-dataset, then a market-level go/no-go.

The decisive question for LotScope is not "does a parcel layer exist" — it's whether the
**zoning-buildability** and **distress** signals that form the moat are machine-ingestible.

---

## Sheriff sales — both markets are CivilView jurisdictions (HIT)

The CivilView platform behind the live PHL sheriff scraper (`salesweb.civilview.com`,
`sheriff_civilview.py`) also serves both targets. The HTTP transport (session/302 handling
hardened this session) reuses directly; the **per-county list column schema differs** and
must be re-mapped, and **parcel reconciliation** has no OPA equivalent (see per-market notes).

| Market | `countyId` | Live rows (recon) | Reuse |
|---|---|---|---|
| Camden County, NJ | `1` | 191 | transport ✅ · parse + reconcile per-market |
| New Castle County, DE (Wilmington) | `24` | 44 | transport ✅ · parse + reconcile per-market |

Column-order caveat (observed): Camden's list row parsed `opa_number` as a date and `address`
as the plaintiff under the PHL column map — `parse_sale_list`/`parse_sale_detail` are
Philadelphia-specific and need a per-county field mapping.

---

## Camden, NJ — verdict: **foundation GO, moat NO-GO**

NJ ships parcels + assessments + last-sale as one `PAMS_PIN`-keyed statewide ArcGIS layer
(NJGIN / MOD-IV) — cleaner than Philly's three-source reconciliation. But the City of Camden's
zoning is not in GIS, and the distress signals are portal/PDF/OPRA-gated.

| Dataset | Verdict | Source / key finding |
|---|---|---|
| Parcels | **GO** | `maps.nj.gov/arcgis/rest/services/Framework/Cadastral/MapServer/0` (HIT) — 191,292 Camden parcels, `PAMS_PIN`, EPSG:3424 (analysis) + 3857/4326 tiles. |
| Assessments / values | **GO** | Same layer: class, land/impr/net value, year built — populated in-sample. |
| Comps | **GO** | MOD-IV last-sale (price/date, HIT) + NJ Treasury **SR1A** flat files 2020–25 with grantor/grantee **names + verified price**. No hbg/pgh party-name wall. |
| Owner identity | **CAUTION** | **Daniel's Law** redaction. Recon conflict: `OWNER_NAME` verified **blank** in 3 samples on the public feed vs a claim that `maps.nj.gov` still exposes it. MUST re-verify — gates owner-side/skip-trace. |
| Zoning districts | **NO-GO (City)** | Only zoning GIS (`CamdenCounty_Zoning_532022/FeatureServer/32`, HIT) codes **all 17,871 City parcels monolithically as `"City"`** — redevelopment plans supersede base zoning. Buildability not resolvable from GIS; only a PDF map + redevelopment-plan PDFs. Ordinance text: eCode360 Ch. 870. |
| Code violations (L&I analog) | **NO-GO** | No dataset / ArcGIS / Socrata. Ordinance text only. |
| Vacancy / abandoned | **NO-GO (data)** | Registry exists administratively (N.J.S.A. 55:19-55); not published — OPRA request. Proxy: MOD-IV vacant-land class. |
| Tax delinquency | **portal-only** | Annual tax-sale portal (`camden.newjerseytaxsale.com`, 403 bot-block) + PDF. NJ sells lien *certificates* — different distress semantics. |
| Public / redevelopment land | **PARTIAL** | No standalone dataset; derive CRA / City / Improvement-Authority parcels from MOD-IV owner + public class (15A–15F). |

**Bottom line:** Camden is buildable as a parcel + valuation + sheriff + comps product — the
foundation is strong and clean — but the zoning-reasoning and distress moat would require heavy
manual PDF digitization + records requests that the open-data stack does not supply.

**Unverified (follow-ups):** an actual SR1A file parse; a bulk owner-name source; the tax-sale
portal contents (403); the CRA inventory (connection refused).

---

## Wilmington, DE (New Castle County) — verdict: **core GO, distress CAUTION**

Wilmington has no own parcel/assessment stack — parcels + assessment are New Castle County (NCC);
statewide geometry is DE FirstMap. It **clears the two bars Camden failed**: per-parcel zoning
GIS exists, and owner names are public (no Daniel's Law).

| Dataset | Verdict | Source / key finding |
|---|---|---|
| Parcels | **GO** | FirstMap `DE_StateParcels/FeatureServer/0` (HIT) — 203,757 NCC parcels, 10-digit `PIN`, EPSG:2776. NCC's own GIS mirror is WAF-blocked; FirstMap is the clean path. |
| Owner identity | **GO** | **Public** (DE FOIA; no Daniel's Law). Present in the NCC parcel product — the differentiator Camden lacked. |
| Assessments / values | **PARTIAL** | Fresh **FMV as of 2024-07-01** reassessment (first in ~40yr). But NCC's `.gov` tier is behind a **Link11 WAF (HTTP 471)** — ingest via ArcGIS Hub GDB/Shapefile download or a data request, not REST. Dollar-value fields in the free GDB unverified. |
| Zoning districts | **GO** ✅ | City ArcGIS org `services.arcgis.com/hQ3wdpbjO3fPf612` — `LUP_Map…/FeatureServer/18` "City Zoning" (HIT): **24 differentiated codes** (R/C/M/W/O families, human-readable descs) via live groupBy; also stamped on all 26,106 parcels via `ZONECODE` (normalize the `26` hundred-prefix). Ordinance on Municode (needs browser-grade scrape). |
| Comps | **PARTIAL (weak)** | Prices/dates/parties public (DE FOIA) but **no bulk feed** like `rtt_summary`. Source via Recorder per-document (DTS PAXWorld), assessment "last sale" (WAF'd), a data request, or a licensed vendor. Weakest leg. |
| Sheriff sales | **GO** | CivilView `countyId=24`, 44 rows. DE "monition" process. |
| Code violations (L&I analog) | **CAUTION** | Portal-only — BuildingBlocks (Tolemi), MUNIS self-service, OpenGov. No bulk/API export. Needs FOIA / Tolemi agreement / scrape / proxy. |
| Vacancy / abandoned | **NO-GO (data)** | Mandatory VPR program exists; registry **not published** (likely inside BuildingBlocks). FOIA path. |
| Public / land bank | **PARTIAL** | `LandBankSideLotParcels_Web_WilmDE` (HIT) — but only **32 side-lot parcels**; full city-owned inventory needs another source. |

**Not verified:** free NCC GDB value-field schema; a bulk sales export; Municode zoning chapter
(403 to automation); whether FirstMap's statewide permits layer covers Wilmington L&I.

---

## Head-to-head & recommendation

The deciding axes are **per-parcel zoning GIS** and **public owner names** — the two pillars of
LotScope's "what can be built / who owns it" value. Camden fails both; Wilmington clears both.

| Axis | Camden, NJ | Wilmington, DE |
|---|---|---|
| Parcel spine | ✅ clean (single MOD-IV layer) | ✅ clean (FirstMap) |
| **Zoning buildability (moat)** | ❌ monolithic `"City"`, PDF only | ✅ 24 real district codes, per-parcel |
| **Owner identity** | ❌ redacted (Daniel's Law) | ✅ public (DE FOIA) |
| Comps | ✅ MOD-IV + SR1A (names+price) | ⚠️ public but no bulk feed |
| Assessment ingestion | ✅ clean REST | ⚠️ WAF-blocked → Hub download / request |
| Sheriff | ✅ CivilView (1) | ✅ CivilView (24) |
| Distress (violations/vacancy) | ❌ portal/OPRA only | ⚠️ portal only (BuildingBlocks/MUNIS) |

**Recommendation: Wilmington first; Camden deferred.** Wilmington supports the *core* product
(zoning buildability + valuation + public owner + sheriff + comps-with-effort); its gaps
(WAF assessment ingestion, no bulk comps feed, portal-only distress) are **engineering/acquisition
tasks**. Camden's zoning gap is a **structural product hole** — no amount of plumbing conjures
per-parcel zoning that the city doesn't publish; it would demand digitizing a PDF map + dozens of
redevelopment plans. Both share the portal-only distress weakness, so **neither is Philly-parity
out of the box** — a Wave-2 launch would gate on a distress-signal sourcing decision regardless.

### What a Wilmington build would entail
- **Reuse:** CivilView sheriff (`countyId=24` + a per-county list-column map), market-scope infra,
  the zoning-resolution/by-right engine (district polygons → buildability, PHL pattern).
- **New loaders:** FirstMap parcels; NCC assessment via **Hub GDB download** (not REST — WAF);
  Wilmington zoning (City ArcGIS org); comps (**needs a sourcing decision** — vendor vs Recorder scrape).
- **Design-around caveats:** NCC WAF; reassessment vintage (FMV 2024-07-01); `26`-prefix zoning
  normalization; no bulk comps; distress via Tolemi/FOIA/proxy.
- **Tripwire:** a Wilmington **distress scoring profile** must be registered (precompute fails without one).

### Open decisions before a kickoff ADR
1. Is a market launch acceptable **without a Philly-grade distress layer** (both candidates lack it)?
2. **Comps sourcing** for Wilmington — licensed vendor (Regrid/ATTOM) vs Recorder/assessment scrape.
3. Owner PII posture for DE (public, unlike NJ) — enables owner-side surfaces if wanted.
