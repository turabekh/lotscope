# PRD Amendment 02 — Geographic Expansion (Multi-Market LotScope)

| | |
|---|---|
| **Status** | Draft for review |
| **Date** | 2026-07-04 |
| **Amends** | `docs/PRD.md`; follows `PRD-amendment-01-monetization.md` |
| **Sequencing** | Executes **after** Amendment 01 Phases 0–1 (revenue attach). Platform prerequisites here (B1–B4) may be batched with Amendment 01's raw-landing/ELT work and its planned `VERDICT_VERSION` v6 bump to avoid recompute thrash (per the ADR-0028 batching principle). |
| **ADRs to author** | ADR-0029 market entity & canonical parcel key · ADR-0030 multi-CRS geometry · ADR-0031 ingestion transports & market-keyed loader registry · ADR-0032 per-market zoning authoring · ADR-0033 vacancy derivation · ADR-0034 per-market distress/forced-sale semantics |
| **Workstreams** | B1–B12 (continues Amendment 01's A1–A11 numbering) |

---

## 0. Executive summary

LotScope's moat is depth-in-one-market; its ceiling is the same thing. Amendment 01 addresses the revenue ceiling (attach: skip trace, export, repositioned tiers). This amendment addresses the TAM ceiling: a repeatable playbook for standing up new markets, and a researched, ranked selection of the **next five cities**.

Nine markets were evaluated against hard data gates and a weighted score (§2–3). The selected roadmap:

> **Wave 0 (pilot):** Harrisburg city — small, relationship-backed, forces the multi-market abstractions while stakes are low.
> **Wave 1:** **Pittsburgh** — near-drop-in data via WPRDC, same-state legal semantics, same map projection; the cheapest real market we will ever add.
> **Wave 2:** **Baltimore** — the best raw product-market fit on the East Coast (published vacancy inventory, 6–10k liens sold at tax sale annually, free statewide deed images); first out-of-state build.
> **Wave 3:** **Detroit** — largest vacant-land inventory in the country, ArcGIS transport we already have; land-bank-aware distress modeling required.
> **Wave 4:** **Milwaukee** — daily master property file (MPROP), monthly delinquency feed, vacant-land sales history; CKAN transport reused from Wave 1.
> **Wave 5:** **Cleveland** — county fiscal GIS hub + active investor demand; weakest delinquency feed of the five, staged last.
>
> **Stretch (Wave 6, separately gated):** Chicago/Cook County — the best assessor open data in the country, but 10× our current scale and a new transport; do not attempt solo before Waves 1–2 prove the playbook.
> **Watchlist:** St. Louis (partial-disclosure carve-out; bulk sales feed unverified). **Rejected for now:** Washington DC (data superb, distress-supply thesis mismatch); county-wide plays anywhere (zoning multiplication, §2.3).

Total selected footprint at Wave 5: roughly **+1.05M parcels** on top of Philadelphia's 550k (Harrisburg-city ~25k of Dauphin's 117.6k, Pittsburgh-city ~150k, Baltimore ~237k, Detroit ~380k, Milwaukee ~160k, Cleveland ~160k), across four states, five upstream transports, and six zoning codes.

The platform cost is front-loaded and paid once: a `market` entity and canonical parcel key (B1), per-market CRS (B2), a transport/loader registry (B3), and per-market reconciliation (B4). After that, each wave is dominated by two knowable tasks — **zoning authoring** and **source adapters** — plus one market-specific distress-semantics mapping. Everything else in the product (verdict composition, AVM math, deal engine, checklist, alerts, watchlists, pipeline, dossier, Ask-the-Parcel machinery) transfers unchanged.

---

## 1. Goals and non-goals

**Goals**

1. Select the next five expansion markets on evidence, with per-market data-source inventories mapped loader-by-loader to the existing Philadelphia stack, and gaps marked.
2. Specify every platform change required for multi-market operation, tied to the exact current behavior in code, with migration notes and ADR ownership.
3. Define a repeatable **New-Market Playbook** (checklist + estimates + launch gates) so each wave is execution, not invention.
4. Preserve the product's epistemics: provenance, honest degradation, and per-market confidence. A market with a weaker signal (e.g., no violations feed) launches with that panel degraded and labeled, never faked.

**Non-goals**

- Rebranding beyond noting the "PHL"-suffix question (a decision, not a workstream here).
- Nationwide/Regrid-first coverage. Regrid remains a per-market *fallback* for base parcels/ownership (token exists), not the strategy; the differentiator layers (delinquency, violations, sales prices, zoning math) are exactly what Regrid does not solve.
- Multi-tenant/team features, i18n, or infrastructure re-platforming (stay on the VM + docker-compose until load data says otherwise; §B12).
- County-wide expansion anywhere (see the scoping rule, §2.3).

---

## 2. Selection framework

### 2.1 Hard gates (a market must pass all five or it is out)

| Gate | Why it is non-negotiable | Philadelphia equivalent |
|---|---|---|
| **G1. Public sale-price disclosure** | The AVM and ARV are built on real recorded prices. A non-disclosure jurisdiction kills the valuation and deal engines outright. | RTT (`rtt_summary`) |
| **G2. Machine-readable parcel geometry** | All spatial math (setbacks, adjacency, overlays, landlocked) runs on polygons. | PWD parcels |
| **G3. Machine-readable assessment/ownership spine** | The parcel record: owner, mailing address, values, dimensions, land use. | OPA (`opa_properties_public`) |
| **G4. A tax-distress signal** | The motivated-seller engine is the top-of-funnel product. Some machine-usable delinquency/forced-sale feed must exist (even if annual). | Revenue delinquency + sheriff-sale flag |
| **G5. One unified zoning code at the chosen scope** | Zoning authoring is the dominant per-market cost; it must be bounded to one ordinance. | Title 14 |

### 2.2 Weighted score (applied to gate-passers)

Distress + vacant supply (25%) · investor/wholesaler demand and distribution reachability (20%) · data richness & freshness across the eleven loader slots (20%) · transport fit with existing/planned clients (10%) · legal-process reuse from PA (10%) · TAM in parcels and plausible subscribers (10%) · deed/recorder accessibility for the documents feature (5%).

### 2.3 The scoping rule: expand by city-with-one-code, never by county

Zoning re-authoring dominates wave cost. Dauphin County contains ~40 municipalities and Allegheny County contains 130 (WPRDC), **each with its own zoning ordinance**. A county-wide launch multiplies the most expensive task by the municipality count for marginal TAM. Therefore: ingest county-level *data* wherever the county is the publisher (assessments, sales, liens are county functions in PA/OH), but **launch, score, and market city-scoped** — parcels outside the launch city are loaded but flagged `coverage='data_only'` (no zoning verdict, honest degradation) or filtered at ingest. This rule alone reframes "Harrisburg/Dauphin" as "Harrisburg city, fed by Dauphin County data."

---

## 3. Candidate scorecard (nine markets evaluated)

Verification status: ✅ = confirmed against the live portal/catalog during research for this PRD; ◐ = dataset known to exist, field-level verification deferred to the wave's ingestion slice (the standing `data-sources.md` practice); ✗ = confirmed gap.

| Market (scope) | ~Parcels | Transport(s) | Sales/comps (G1) | Delinquency/distress (G4) | Violations | Vacancy signal | Zoning lift | Decision |
|---|---|---|---|---|---|---|---|---|
| **Pittsburgh** (city; county data) | ~150k city / ~583k county | CKAN datastore + ArcGIS ✅ | ✅ County sale transactions w/ validation codes | ✅ Tax liens (1995→, monthly) + city delinquency dataset + foreclosures | ✅ PLI violations + condemned/"dead-end" | ◐ Derived (land use + improvement≈0) + condemned | One city code | **Wave 1** |
| **Baltimore** (city) | ~237k | ArcGIS Hub ✅ + SDAT | ✅ SDAT sale history; city Real Property | ✅ Annual tax sale (6–10k liens/yr) ◐ list format | ◐ City code-enforcement datasets | ✅ **Vacant Building Notices, daily** + Vacants-to-Value city inventory | One city code (2017 rewrite) | **Wave 2** |
| **Detroit** (city) | ~380k | ArcGIS Hub ✅ (existing client) | ✅ Property Sales dataset (MI = disclosure) | ◐ Wayne Co. forfeiture/foreclosure pipeline; auction lists | ✅ Blight violations | ✅ DLBA inventory + assessor land use | One city ordinance | **Wave 3** |
| **Milwaukee** (city) | ~160k | CKAN ✅ + ArcGIS REST | ✅ Sales history incl. **vacant-land sales**; MPROP daily | ✅ Delinquent RE tax accounts, monthly | ◐ DNS violations not fully open (request/scrape) ✗ | ◐ City vacant-buildings + foreclosure layers; lots derived | One city code | **Wave 4** |
| **Cleveland** (city; county data) | ~160k city / ~520k county | ArcGIS (Fiscal GIS Hub) ✅ | ✅ County parcels+values+recent sales (OH = disclosure) | ◐ Annual delinquent list (newspaper-grade); forfeited-lands sale | ◐ City Building & Housing layers | ◐ Derived + county land bank inventory | One city code | **Wave 5** |
| **Chicago** (city; Cook data) | ~880k city / 1.8M PINs | Socrata (new) ✅ | ✅ Assessor Parcel Sales 1999→, monthly, arms-length flags | ◐ Treasurer annual/scavenger sale (not clean open data) | ✅ City building violations | ◐ Derived + city vacant-buildings reports | One city ordinance, large | **Stretch / Wave 6 gate** |
| **Harrisburg** (city; Dauphin data) | ~25k city / 117.6k county | ArcGIS Hub + **periodic extracts** ✅ | ◐ PA disclosure; recorder/extract sale fields to verify | ◐ Tax Claim Bureau (RETSL upset/judicial) — list format to verify | ✗ No open code-enforcement dataset | ◐ Derived only | One small city code | **Wave 0 pilot** |
| St. Louis (city) | ~130k | Socrata/city | ◐ MO is non-disclosure **except** St. Louis City/County & Jackson Co. (certificates of value; city site shows prices) — bulk feed unverified | ◐ LRA inventory strong; delinquency feed unverified | ◐ | ✅ LRA/vacancy strong | One city code | **Watchlist** (re-evaluate after Wave 2) |
| Washington DC | ~200k | ArcGIS/Socrata | ✅ | ◐ Annual tax sale small | ✅ | ◐ Vacant/blighted list exists | One code | **Deferred** — distress-supply thesis mismatch (low vacancy, high prices); revisit if persona broadens |

Camden/Chester/Norristown are noted as near-zero-distribution-cost adjacencies (Philly REIA already buys there) but fail the TAM bar as standalone waves; they are candidates for a later "metro add-on" batch under the same playbook.

---

## 4. The five selected markets — deep profiles

Each table maps the eleven Philadelphia loader slots to the market's equivalent. "Slot" names match `lotscope.ingestion.loaders.*`. Anything marked ◐ is verified-to-exist but field-mapped during that wave's ingestion slice, exactly as `docs/data-sources.md` handled Philadelphia ("plausible but verify against the live API").

### 4.1 Wave 1 — Pittsburgh, PA (city scope; Allegheny County data)

**Snapshot.** Legacy-city vacancy concentrated in Homewood, Larimer, the Hill District, and the Mon Valley edge neighborhoods; an active flip/wholesale scene; a city Land Bank. County publishes through the **Western Pennsylvania Regional Data Center** (WPRDC, `data.wprdc.org`) — a University of Pittsburgh/City/County partnership and the closest thing to a second OpenDataPhilly in the country, including a per-parcel **Property API** that bundles assessments, sales, delinquency, city-owned, and foreclosure records in one call.

| Slot (Philly loader) | Pittsburgh source | Transport | Status / gotchas |
|---|---|---|---|
| `opa` (spine) | **Allegheny County Property Assessments** — parcel-level land/building values, owner, land use, lot data; monthly archives + data dictionary | CKAN datastore (SQL queries supported) | ✅. County-wide; filter to Pittsburgh municipality codes at load. **Ordinance 3478-07 prohibits owner-name search on county records** — data carries owner fields, but Leads/owner-portfolio need a compliance read before launch. |
| `pwd` (geometry) | Allegheny County parcel boundaries (join key = 16-char block-lot parcel ID) | CKAN / ArcGIS | ✅. Same PA South plane as Philadelphia → **zero SRID work this wave** (B2 dry run only). |
| `rtt` (sales/comps) | **Property Sale Transactions** (county Real Estate Division) with **sales-validation codes** — e.g., code "H" marks multi-parcel deeds where the price covers a group | CKAN | ✅. Validation codes are *better* than RTT: filter invalid codes in the loader and comp quality rises. Deeds "not required to be recorded at time of sale" — expect gaps, as in Philly. |
| `tax` (distress) | **Tax Liens (Filings, Satisfactions, Current Status)** — county/municipal/school/water-sewer liens since 1995, monthly; **City of Pittsburgh Property Tax Delinquency** (all delinquent city parcels per levy year); **foreclosures** dataset | CKAN | ✅. Lien docket numbers are **not unique** — key on docket+year+description, per the publisher's own note. |
| `li_*` (violations) | City **PLI violations**; **condemned properties incl. "dead-end"** (owner unlocatable — a distress gem Philly lacks) | CKAN | ✅. Map condemned→`unsafe_structure`-class severity; "dead-end" is a new high-value distress factor. |
| `zoning` | City of Pittsburgh zoning districts (single city code) | ArcGIS/CKAN | ◐ layer; **authoring the Pittsburgh code into `zoning_standard` + corpus is the wave's dominant task** (B5). |
| `vacancy` | No city vacancy model → **derived** (B6): vacant land-use class + improvement value ≈ 0, cross-checked with condemned/city-owned | — | ◐ derivation; `vacancy_confidence` reflects method. |
| `flood` | FEMA NFHL (national) | ArcGIS | ✅ same loader, new extent. |
| `neighborhoods` | City neighborhoods layer (90 official) | ArcGIS/CKAN | ✅. |
| `streets` | City/county centerlines | ArcGIS | ✅ same pattern as ADR-0027. |
| `historic` | City historic districts (Historic Review Commission) | ArcGIS | ◐; same overlay pattern as ADR-0028. |
| Publicly owned | **City-owned properties** (eProperties Plus) + Pittsburgh Land Bank inventory | CKAN | ✅ feeds `is_city_owned` (distress score 0 rule transfers). |

**Distress semantics (ADR-0034 entry).** Same state, near-identical meaning: PA MCTLA-style treasurer/sheriff enforcement; `in_sheriff_sale` maps to the city treasurer-sale/foreclosure pipeline. The lien dataset gives the strongest lien signal of any market including Philadelphia.
**Deeds.** Allegheny recorder documents are behind the county real-estate portal; ship the compliant **index + deep-link** pattern from ADR-0026 with a per-market URL template; text analysis stays upload/ToS-gated.
**Wave-specific work.** New CKAN datastore client (also serves Milwaukee); Pittsburgh zoning authoring; sales-validation filter; condemned/dead-end distress factors; owner-name compliance memo.
**Risks.** Owner-name ordinance interpretation; county-vs-city coverage boundary confusing users (mitigate: `data_only` badge outside city limits); WPRDC Data Use Agreement review for commercial use per dataset license.

### 4.2 Wave 2 — Baltimore, MD (city scope)

**Snapshot.** The strongest distress supply on the East Coast: ~237,403 parcels; ~14–15k open **Vacant Building Notices**; ~7,900 additional city-owned derelict vacant lots; **6,000–10,000 property liens sold at the annual tax sale**. A huge wholesaling culture and a city that literally publishes its vacancy problem as open data, daily. First out-of-state wave — this is where B2 (CRS), ADR-0034 (new forced-sale semantics), and a new title quirk (ground rent) all fire for real.

| Slot | Baltimore source | Transport | Status / gotchas |
|---|---|---|---|
| `opa` | **Real Property Information** (Open Baltimore) parcel-level; backed by **MD SDAT** statewide assessments (owner, values, **deed liber/folio reference**, sale history) | ArcGIS Hub + SDAT | ✅/◐. SDAT does not search by owner name (address/account/map only) — same compliance posture as Allegheny for anything owner-search-shaped. |
| `pwd` | City parcel polygons (Open Baltimore) | ArcGIS Hub | ✅. Keying is **ward-section-block-lot** — reconciliation adapter (B4). MD state plane (ft, EPSG:2248) — first non-2272 market. |
| `rtt` | SDAT sale history + city Real Property transfer fields (MD is a full-disclosure state) | SDAT/ArcGIS | ◐ field mapping; comp engine unchanged. |
| `tax` | **Annual tax-sale eligibility list** (6–10k liens/yr) + city liens/receivables | List/CSV + ArcGIS | ◐ format verification; the tax-sale *calendar* itself becomes a headline feature here (Amendment 01's sheriff/tax-sale calendar item lands first in Baltimore). |
| `li_*` | City code-enforcement / housing citations; demolition datasets | ArcGIS Hub | ◐. |
| `zoning` | TransForm Baltimore (2017 single-code rewrite) districts | ArcGIS Hub | ◐ layer ✅ concept; second-largest authoring job of the program (B5). |
| `vacancy` | **Vacant Building Notices (daily)** for structures + city vacant-lot flags + derived-lot fallback | ArcGIS Hub | ✅ — the best explicit vacancy signal of any market, Philadelphia included. VBN covers *buildings*; lots still use B6 derivation. |
| `flood` | FEMA NFHL | ArcGIS | ✅. |
| `neighborhoods` | City neighborhoods layer | ArcGIS Hub | ✅. |
| `streets` | City centerlines | ArcGIS Hub | ✅. |
| `historic` | CHAP local historic districts | ArcGIS Hub | ◐. |
| Publicly owned | **Vacants-to-Value open-bid list** (city-owned inventory actually for sale) | ArcGIS Hub | ✅ — richer than a flag: it is a *disposition pipeline*, surfaced as its own acquirability status in assemblage/leads. |

**Distress semantics.** Maryland runs a **tax-lien certificate sale** (certificate → redemption interest → foreclosure), not a PA sheriff sale. Mapping: `on annual tax-sale list` carries the sheriff-sale weight (30); post-sale certificate/foreclosure status upgrades severity. New **`ground_rent` risk flag** (SDAT ground-rent registry): a leasehold quirk unique to Baltimore that locals will judge the product's credibility by.
**Deeds — the unlock.** Maryland land records (deeds, mortgages, liens, plats) are viewable **free** at the state archives portal (mdlandrec.net → landrec.msa.maryland.gov) after free registration, and SDAT hands us the per-parcel **liber/folio** pointer. This flips ADR-0026's economics: Philadelphia's index-plus-paywalled-deep-link becomes index-plus-**free**-deep-link, and (pending Archives Acceptable-Use/ToS review) a credential-gated `DeedSource` adapter could make Baltimore the first market with real at-scale deed RAG.
**Wave-specific work.** B2 in anger (2248); reconciliation for block-lot keys; tax-sale list ingest + calendar surface; ground-rent flag; VBN vacancy integration; MDLandRec adapter behind ToS gate; zoning authoring.
**Risks.** Tax-sale list machine-readability (fallback: annual CSV/PDF parse, freshness labeled); ground-rent registry access pattern; two-source spine (city + SDAT) drift — reconcile explicitly and record provenance per field.

### 4.3 Wave 3 — Detroit, MI (city scope)

**Snapshot.** The largest vacant-land inventory in the U.S.; the **Detroit Land Bank Authority is the city's largest property owner**, with its full inventory (address, parcel number, status) published as open data. Michigan is a disclosure state. The transport is ArcGIS Hub end-to-end — the client we already run — making Detroit the *lowest adapter-cost* wave despite being the most distinctive market.

| Slot | Detroit source | Transport | Status / gotchas |
|---|---|---|---|
| `opa` | Assessor parcel dataset (ownership, values, characteristics; per-tax-year) | ArcGIS Hub | ✅ ("Parcels (Current)", 2026 tax year noted on portal). |
| `pwd` | Same assessor parcel polygons | ArcGIS Hub | ✅. MI state plane (intl-ft variant — pin exact EPSG at wave ADR; B2). |
| `rtt` | **Property Sales** dataset | ArcGIS Hub | ✅ dataset ◐ fields. Very low nominal-price transfers are common (DLBA $100 lots) — the AVM's existing ≥$1,000 floor plus a DLBA-transfer filter keeps comps honest. |
| `tax` | Wayne County treasurer **forfeiture → foreclosure → auction** pipeline (PA 123: 3-year cycle) | County lists ◐ | ◐ — the one genuinely uncertain feed; fallback is the annual auction list + city "back taxes" fields. Gate the wave on locating a usable feed. |
| `li_*` | **Blight Violations** (blight tickets) | ArcGIS Hub | ✅ — maps cleanly onto the violations slots; demolition program datasets also published. |
| `zoning` | Detroit Zoning Ordinance (single ordinance; R/B/M district families) | ArcGIS Hub | ◐ layer; authoring job comparable to Pittsburgh's. `land_use_class` prefix map needs a per-market table (B5): Detroit "B" = business → commercial. |
| `vacancy` | **DLBA inventory** + assessor land use + derived fallback | ArcGIS Hub | ✅ strongest *inventory* signal anywhere — but see distress note. |
| `flood` / `neighborhoods` / `streets` | FEMA; city neighborhoods; centerlines | ArcGIS | ✅. |
| `historic` | Local historic districts (HDC) | ArcGIS | ◐. |
| Publicly owned | DLBA Owned Properties + city-owned | ArcGIS Hub | ✅. |

**Distress semantics.** `in_sheriff_sale` maps to the **forfeiture/foreclosure pipeline stage**; the annual Wayne County auction is the calendar event. Critically, the existing rule *city/land-bank-owned scores 0* does heavy lifting here: a large share of Detroit's vacant lots are DLBA-owned and therefore **not private-seller leads** — raw vacancy overstates the lead pool, and the product must say so. Conversely, DLBA's public *disposition* programs (side lots, auctions) become a first-class acquirability channel in assemblage and a possible dedicated surface.
**Deeds.** Wayne County register is paid; index + deep-link only.
**Wave-specific work.** Distress-pipeline mapping + auction calendar; DLBA acquirability channel; comp filters for nominal transfers; MI CRS pin; zoning authoring.
**Risks.** Delinquency feed quality (wave gate); very low price points stress the $99–249 willingness-to-pay — validate with 25 design partners before full build; Regrid's home-turf competitive presence.

### 4.4 Wave 4 — Milwaukee, WI (city scope)

**Snapshot.** The famous **MPROP** master property file: ~160k parcels, 90+ fields, **updated daily** since 1975 — the single richest municipal spine file in this program. Monthly **delinquent real-estate tax accounts**, a sales-history dataset that explicitly includes **vacant-land sales**, and GIS layers for tax delinquency, vacant buildings, city-owned inventory, and per-parcel foreclosure status. In-rem foreclosure (the city forecloses directly) supplies both distress signal and city-owned inventory.

| Slot | Milwaukee source | Transport | Status / gotchas |
|---|---|---|---|
| `opa` | **MPROP** daily CSV/datastore (owner, mailing, values, land use, dims; TAXKEY key) | CKAN (client from Wave 1) | ✅. **Caveat from the publisher:** tax-exempt, manufacturing, and *city-owned* records are limited/not maintained in MPROP — pair with the city-owned GIS layer or those parcels degrade. |
| `pwd` | Parcel polygons (join on TAXKEY) | CKAN/ArcGIS REST (`milwaukeemaps`) | ✅. WI state plane (ft) — pin EPSG at wave ADR. |
| `rtt` | **Sales history** dataset (residential/condo/commercial/apartments **and vacant land**), yearly refresh; WI is a disclosure state (transfer returns) | CKAN | ✅ dataset ◐ cadence — yearly refresh means comp freshness lags; supplement from MPROP last-sale fields (which update daily) and label freshness per source. |
| `tax` | **Delinquent Real Estate Tax Accounts** — monthly, per levy year, principal-only amounts | CKAN | ✅. Amount due excludes interest/penalties — label it (honest degradation), severity thresholds recalibrated in ADR-0034. |
| `li_*` | DNS code-enforcement violations | — | ✗/◐ **not fully open** (third parties obtain it "by special request"). Launch options: (a) data request to DNS, (b) permits-only degrade with the violations checklist row marked *no data source*, never silently green. |
| `zoning` | City zoning (nightly-refreshed layer) | ArcGIS REST | ✅ layer; authoring job (B5). |
| `vacancy` | City **vacant buildings** + **foreclosure status** layers + derived lots | ArcGIS REST | ✅/◐. |
| `flood` / `neighborhoods` / `streets` | FEMA; city layers | ArcGIS | ✅. |
| `historic` | Local historic districts (HPC) | ArcGIS | ◐. |
| Publicly owned | City-owned real-estate inventory (in-rem stock) | ArcGIS REST | ✅. |

**Distress semantics.** `in_sheriff_sale` maps to **in-rem foreclosure status**; monthly delinquency drives the delinquent factors.
**Deeds.** Milwaukee County register (LandShark) is paid; index + deep-link only.
**Wave-specific work.** MPROP field mapping (90+ fields — biggest transform of the program, but the documentation PDF is excellent); daily-file extract scheduling; DNS violations request; zoning authoring.
**Risks.** Violations gap is the product's most visible degrade of the five (Risk tab thinner); yearly sales-file cadence vs. daily MPROP creates mixed freshness that provenance labeling must carry.

### 4.5 Wave 5 — Cleveland, OH (city scope; Cuyahoga County data)

**Snapshot.** A national magnet for out-of-state investors; the pioneering **Cuyahoga Land Bank**; county data centralized on the **Fiscal GIS Hub** (parcels, values, recent sales, downloadable + REST). Ohio is a disclosure state (conveyance-fee records). Staged last of the five because its distress feed is the weakest: the county's delinquent list is a statutory *annual newspaper publication*, not a clean monthly dataset, plus a forfeited-lands sale list.

| Slot | Cleveland source | Transport | Status / gotchas |
|---|---|---|---|
| `opa` | Cuyahoga Fiscal Office parcel/assessment data (MyPlace-backed; hub extracts) | ArcGIS (Fiscal GIS Hub) | ✅ hub ◐ fields. County-wide; city-scope filter at load. |
| `pwd` | County parcel polygons | ArcGIS | ✅. OH North plane (ft) — pin EPSG at wave ADR. |
| `rtt` | County "recent sales" / conveyance records via hub extracts | ArcGIS/extract | ✅ concept ◐ depth — verify history length; supplement recorder if shallow. |
| `tax` | **Annual delinquent tax list** (statutory publication) + **Forfeited Lands Sale** parcel listing + Board-of-Revision foreclosure records | List/extract | ◐ — annual cadence means distress freshness is labeled *as of publication*; BOR foreclosure docket scrape is a stretch item. This is why Cleveland is Wave 5. |
| `li_*` | City Building & Housing code-enforcement / condemnation / demolition layers | City ArcGIS portal | ◐. |
| `zoning` | Cleveland zoning code (single) + districts layer | City ArcGIS | ◐; authoring job (B5). |
| `vacancy` | Derived + **Cuyahoga Land Bank** inventory | — | ◐. |
| `flood` / `neighborhoods` / `streets` | FEMA; city layers | ArcGIS | ✅. |
| `historic` | Cleveland Landmarks districts | ArcGIS | ◐. |
| Publicly owned | Land bank + city-owned | ArcGIS/extract | ✅ concept. |

**Distress semantics.** Ohio mixes **tax-certificate sales to third parties**, BOR expedited foreclosure for vacant/abandoned, and forfeited-lands auctions — the most fragmented mapping of the five; ADR-0034 gets its stress test here.
**Deeds.** Cuyahoga recorder offers free online document search; index + deep-link, adapter feasibility ◐.
**Risks.** Distress freshness (annual) undercuts the alerts value-prop — set expectations in-product; two-portal stack (county fiscal + city) needs the same dual-source provenance discipline as Baltimore.

---

## 5. Platform workstreams — how the current code changes (B1–B12)

Each workstream states the **current behavior** (as it exists in the codebase today), the **target behavior**, and migration/ADR notes. B1–B4 are prerequisites for any second market, including the Wave-0 pilot; B5–B12 land with the waves that first need them.

### B1 — Market entity & canonical parcel key *(ADR-0029; prerequisite)*

**Today.** There is no market concept. `parcel.parcel_number` (`String(20)`) is the primary key, semantically the Philadelphia OPA 9-digit account; every child table (`sale`, `tax_status`, `li_event`, `parcel_verdict`, `parcel_distress`, `saved_parcel`, `deal`, `saved_search_match`, `deed_document`) carries a `parcel_number` FK with `ON DELETE CASCADE`. Philly-specific reconciliation columns `pwd_parcel_id` and `brt_number` sit on the parcel row. Allegheny's 16-char block-lot IDs, Baltimore's ward-section-block-lot, Milwaukee's 10-digit TAXKEY, and Cook's zero-padded 14-digit PINs all collide with none of these assumptions except by luck.

**Target.**
- New `market` table: `code` (pk: `phl`, `hbg`, `pgh`, `bal`, `det`, `mke`, `cle`), `name`, `state`, `local_srid`, `map_center`, `map_bounds`, `default_zoom`, `timezone`, `recorder_url_template`, `deal_assumption_overrides` (jsonb), `coverage_note`, `launch_status` (`live` / `data_only` / `pilot`).
- **Canonical parcel key = `{market}:{local_key}`** (e.g., `phl:012345678`, `pgh:0028F00194000000`), preserving the single-column PK so every existing FK, cascade, upsert helper, and the keyset-pagination chunker survive untouched. `parcel` gains `market_code` (FK, indexed) and `local_key` (the bare upstream key) as generated/stored convenience columns.
- Philly-specific `pwd_parcel_id` / `brt_number` fold into a `source_keys` jsonb (per-market alternate keys), retained as columns until Wave 1 for compatibility.

**Migration.** One-time rewrite of all `parcel_number` values to `phl:`-prefixed keys across all tables (transactional, scripted, verified by row counts); an API/URL compatibility resolver accepts bare 9-digit keys for `phl` indefinitely (old links, PDFs, and bookmarks keep working). `String(20)` widens to `String(40)`.
**Why not a composite PK.** `(market_code, parcel_number)` ripples a two-column FK through nine-plus tables, every raw-SQL join in the services, and the MVT functions — maximal churn for zero capability the prefixed key doesn't provide.

### B2 — Multi-CRS geometry *(ADR-0030; prerequisite, trivial until Wave 2)*

**Today.** Every spatial table declares `geom_2272` with SRID 2272 (PA South, US ft) baked into the GeoAlchemy2 column, plus `geom_4326` for tiles; all engine SQL does feet-denominated math on `geom_2272` (`ST_DWithin(..., 2.0)` adjacency, 75 ft street test, `ST_Buffer(geom_2272, -inset)` envelope, 1,500 ft comps radius).

**Target.** Rename `geom_2272` → **`geom_local`** with the SRID constraint relaxed (typmod SRID 0; GiST index unchanged), and `market.local_srid` recording each market's **foot-based** state-plane EPSG. All feet constants stay literal — the invariant is *"`geom_local` is always a ft-denominated plane"*, so no engine math changes. Ingestion derives `geom_local` via `ST_Transform(geom, market.local_srid)` and `geom_4326` as today.
**The one real rule this creates:** every cross-parcel spatial query (assemblage neighbors, comps, street/historic/flood intersects) must carry a `market_code` predicate, both for correctness (mixed-SRID rows must never meet in one `ST_DWithin`) and for index selectivity. These queries are already parcel-anchored, so this is a mechanical audit, enforced by an integration test that plants two markets and asserts isolation.
**Sequencing luck.** Philadelphia, Harrisburg, and Pittsburgh are all PA South (2272) — B2 ships as a rename with zero behavioral change through Wave 1, and fires for real at Baltimore (EPSG:2248). Michigan/Wisconsin/Ohio EPSGs are pinned in each wave's kickoff ADR (Michigan's international-foot vs US-survey-foot nuance is sub-inch at parcel scale but gets recorded).

### B3 — Ingestion transports & market-keyed loader registry *(ADR-0031; prerequisite; batches with Amendment 01's ELT raw-landing layer)*

**Today.** Two clients (`CartoClient`, `ArcGisClient`) with hardcoded singleton base URLs in `Settings` (`carto_sql_url`, `arcgis_hub_url`); `INGEST_JOBS` is a flat `dict[str, Job]` of thirteen Philadelphia jobs; `dataset_freshness` has no market dimension; loaders write normalized rows directly (raw capture deliberately deferred in ADR-0004).

**Target.**
- Registry re-keyed **`(market, dataset) → job`**; `ingest_all` becomes `ingest_market(market)`; `dataset_freshness` gains `market_code`. Admin datasets page groups by market.
- Source endpoints move from `Settings` into per-market source config (data, not code — the ADR-0006 "standards are data" principle applied to ingestion).
- **Transport roster:** keep `CartoClient` (Philly-only, it turns out — no other candidate uses Carto) and `ArcGisClient` (Detroit, Baltimore, Cuyahoga, Dauphin, FEMA, most GIS layers); add **`CkanDatastoreClient`** (WPRDC + Milwaukee; datastore SQL supports the same keyset-chunking discipline as Carto) and **`ExtractClient`** (checksummed file downloads with staging: Dauphin's periodic assessment extracts, Milwaukee's daily MPROP CSV, Baltimore's annual tax-sale list, Cleveland's annual delinquent list). A `SocrataClient` is specced but deferred to the Chicago gate.
- The Amendment-01 **raw landing layer** is the natural home for `ExtractClient` payloads and makes every new-market loader replayable during field-mapping — build them together, once.

### B4 — Per-market key reconciliation *(prerequisite; extends the existing module)*

**Today.** `ingestion/reconciliation.py` normalizes OPA/BRT variants to a canonical 9-digit key — pure, fully unit-tested, and entirely Philadelphian.

**Target.** A `KeyNormalizer` protocol with per-market implementations (Philly 9-digit; Allegheny 16-char block-lot; Baltimore ward-section-block-lot composition; Detroit assessor parcel format; Milwaukee TAXKEY; Cook 14-digit **zero-padded** — the portal itself warns that leading zeros drop in downloads). Same contract as today: misaligned records reconcile or are *reported, never dropped*. Each market's normalizer ships with the golden-file tests the Philly one has.

### B5 — Zoning: market dimension + the authoring playbook *(ADR-0032; per wave)*

**Today.** `zoning_standard` is unique on `(code, code_version)`; the seed (`zoning.seed`) encodes Title 14; `normalize_zoning_code` is generic but `land_use_class` maps prefixes R/C/I/S — a Philadelphia taxonomy; the RAG corpus loads under `source='title14'`; density logic (per-unit-area + FAR) is generic machinery fed by Philly constants.

**Target.**
- `zoning_standard` unique becomes `(market_code, code, code_version)`; district resolution (spatial-first, attribute fallback, method recorded) is already market-agnostic once the districts layer is loaded per market.
- Per-market `land_use_class` mapping table (Detroit "B"→commercial, etc.).
- Corpus rows carry the market (`source='zoning'`, `doc_metadata.market` — no `document` schema change, per the ADR-0026 pattern); retrieval filters by market.
- **The authoring playbook** (the wave's critical path, ~40–50% of wave effort): (1) obtain the official code text → JSONL corpus; (2) seed district taxonomy + the well-established dimensional figures, **leaving unconfirmed fields NULL** so the engine degrades honestly (the ADR-0006 discipline, verbatim); (3) encode density rules only where the corpus states them (the ADR-0014 golden rule — *never from memory*); (4) spot-verify 25 known parcels against the city's own zoning viewer; (5) sign-off ADR per market with `code_version` stamped (`pgh-provisional-2026`, …). Every verdict in a new market launches with zoning confidence honestly capped until step 4 passes.

### B6 — Vacancy derivation engine *(ADR-0033; Wave 1)*

**Today.** `parcel.is_vacant` + `vacancy_confidence` come from one loader: Philadelphia's Vacant Property Indicators model — a luxury almost no other city has.

**Target.** A per-market vacancy strategy behind one interface: **(a) city model** where published (Philly VPI; Baltimore VBN for structures + city lot flags), **(b) derived** elsewhere — vacant land-use class **and** improvement value ≈ 0, optionally corroborated by building-footprint absence and condemned/land-bank status — with `vacancy_confidence` encoding the method (model > multi-signal derived > single-signal). The map legend and filters read identically everywhere; the confidence field carries the honesty.

### B7 — Distress & risk semantic adapters *(ADR-0034; per wave)*

**Today.** `distress/scoring.py` and `risk/scoring.py` are pure and portable — weights, tiers, caps, and the city-owned-scores-zero rule all transfer — but three inputs are semantically Philadelphian: `in_sheriff_sale`, `is_city_owned` (OPA/Land-Bank derivation), and the L&I-shaped violation signals.

**Target.** Signals generalize; scorers don't change. `in_sheriff_sale` becomes the market-mapped **`in_forced_sale_pipeline`** with a per-market label surfaced in flag details (Sheriff sale / Tax-sale certificate list / Forfeiture-foreclosure stage / In-rem / Upset-judicial); `is_city_owned` unions each market's public inventories (city, PHDC, DLBA, Cuyahoga Land Bank, Pittsburgh Land Bank, Vacants-to-Value); new market-specific flags slot into the existing severity scheme (`ground_rent` low/medium — Baltimore; `dead_end_owner` high-value distress factor — Pittsburgh). The DD-checklist categories are unchanged; a market lacking a feed shows that row as *no data source for this market*, never a silent pass. Severity thresholds with dollar semantics (`$10k` severe delinquency) get per-market review in each ADR-0034 entry (Milwaukee's principal-only amounts, Detroit's price levels).

### B8 — Valuation & deal assumptions per market *(Wave 1)*

**Today.** The AVM (1,500 ft / 3 yr / ≥$1,000 / same-use-class / IQR trim / confidence gates) is fully generic. Deal assumptions are **global** `Settings` (`deal_construction_cost_per_sqft=175`, soft 15%, selling 7%, margin 20%) — Philadelphia rowhouse-infill numbers.

**Target.** Comps queries gain the B2 market predicate; loaders apply market-specific validity filters (Allegheny sales-validation codes; Detroit nominal-transfer exclusion). Deal defaults resolve **market → settings fallback** via `market.deal_assumption_overrides`, seeded with placeholder locals to be calibrated with design partners (indicatively: PGH ~$160/sqft, BAL ~$170, DET ~$150, MKE ~$155, CLE ~$150 — placeholders, not authority; every value remains per-request overridable exactly as today). The AVM's honest-degradation behavior needs no change — thin-comp neighborhoods in new markets will correctly read low-confidence from day one.

### B9 — Verdict, versioning, and recompute at scale *(batches with Amendment 01's v6)*

**Today.** `VERDICT_VERSION = "v5"`; contract owned by `verdict/`; the citywide sweep runs ~500 parcels/14s (~4–5h for 550k); nightly vacant-only recompute + Sunday full sweep.

**Target.** Contract unchanged (market rides on the parcel). Fold any expansion-driven field additions into **the same v6 bump Amendment 01 already plans** — one bump, one sweep, per the ADR-0028 lesson. Recompute jobs become per-market (`recompute_market_verdicts('pgh')`); at Wave-5 footprint (~1.6M parcels) the full sweep extrapolates to ~12–13h — acceptable weekly, and per-market staggering keeps any one market's staleness bounded. Cron schedule generalizes to per-market groups with staggered hours (B12).

### B10 — Search, tiles, and frontend market scope *(prerequisite for UX; Slice 1 already shipped)*

**Today.** Trigram search, `/search/area`, saved-search criteria, and leads are implicitly citywide-Philadelphia; Martin serves `parcels_mvt`/`vacant_lots_mvt` over all rows; the frontend's market-scope foundation (URL-authoritative market routing, store rename, search scoping) **shipped in redesign Slice 1** — this workstream is the backend catching up to the frontend's routing primitive.

**Target.** `/search`, `/search/area`, `/leads`, and `SearchCriteria` gain a required `market` (defaulted from route scope); `saved_search` and `neighborhood` rows carry `market_code`; MVT functions add `market_code` to properties (extents don't overlap, so one tile layer serves all markets — the map simply flies to `market.map_bounds` on scope change); Ask-the-Parcel retrieval filters corpus by market. Cross-market surfaces (a unified multi-market deal feed) are explicitly Amendment-03 territory, not this program.

### B11 — Documents & recorder adapters per market *(per wave)*

**Today.** `philadox_document_url_template` is a global setting; the deed feature is the compliant index + deep-link + upload-analyze pipeline of ADR-0026, with `DeedSource` credential/ToS-gated and off by default.

**Target.** `market.recorder_url_template` replaces the global; per-market recorder posture recorded in each wave ADR: Philadelphia PhilaDox (paid) · Allegheny county portal (index/deep-link) · **Maryland landrec.msa.maryland.gov (free images, free registration — candidate for the first live `DeedSource` adapter, pending an Archives Acceptable-Use review)** · Wayne County (paid) · Milwaukee LandShark (paid) · Cuyahoga (free search, feasibility to verify). The upload-analyze path works identically in every market on day one.

### B12 — Accounts, billing, branding, ops *(Wave 1 decisions)*

- **Entitlements:** launch with **all plans, all markets** (a Philadelphia wholesaler gains nothing from a Pittsburgh paywall, and multi-market users are the Investor-tier upsell Amendment 01 prices for). Revisit per-market add-ons only if data costs force it. No `tiers.py` change at launch beyond copy.
- **Branding:** `email_from_name="LotScope PHL"`, the landing hero, and the product name carry a city suffix. Decision needed by Wave-1 launch: market-neutral master brand ("LotScope") with per-market landing pages. Flagged, not solved here.
- **Ops & capacity:** per-market ingest crons staggered (4:00/4:40/5:20…); the e2-standard-4 VM and Postgres are comfortable to ~2M parcels with existing indexes, but the 100GB SSD is not — plan **100→300GB** disk by Wave 3 (dual-geometry rows dominate; Philadelphia's footprint roughly triples). Martin and Redis are unaffected. Backups/restore runbook re-tested at the new size.
- **Legal/ToS ledger (new standing doc, `docs/data-licenses.md`):** per-source license and permitted-use notes — WPRDC Data Use Agreement (per-dataset licenses; commercial-use check), Allegheny Ordinance 3478-07 (owner-name search prohibition — bounds Leads/owner-portfolio UX in that market), Maryland Archives AUP (deed automation), city portal terms elsewhere. Same posture as the PhilaDox resolution in ADR-0026: compliant by construction, degrade rather than scrape.

---

## 6. Execution roadmap

### 6.1 Phase P — Platform prerequisites (before any second market)

B1 key migration · B2 rename + market predicate audit · B3 registry + `CkanDatastoreClient` + `ExtractClient` (batched with Amendment 01's raw landing) · B4 normalizer protocol · B10 backend market scope (meets the shipped frontend Slice 1). Estimated **3–4 weeks** of slices at the current cadence, ending with a two-market integration test suite (synthetic second market) fully green. Exit criterion: Philadelphia runs on the multi-market codebase with **zero user-visible change** — `phl:`-prefixed keys resolving, old URLs working, verdicts byte-identical modulo `computed_at`.

### 6.2 The New-Market Playbook (repeated per wave)

1. **Kickoff ADR** (one per market): scope boundary, `local_srid`, source config, key format, distress mapping (ADR-0034 entry), recorder posture, license ledger entries, deal-assumption placeholders.
2. **Loaders** in the standing order: spine → geometry → sales → tax → violations → zoning layer → vacancy → overlays (flood/historic) → streets → neighborhoods → public-owned. Each loader: raw-landing capture → field mapping recorded in `docs/data-sources-{market}.md` → idempotent upsert → freshness row → golden-file tests.
3. **Zoning authoring** (B5 playbook, steps 1–5) — runs in parallel with loaders; the wave's critical path.
4. **Vacancy strategy** wired (B6) · **distress adapter** wired (B7) · **market-specific flags** added.
5. **Verdict batch compute** for the market; spot-verify the 25-parcel golden set (zoning viewer, county records, a local's eyes).
6. **Data-parity gate** (see 6.4) → soft launch to ~25 design-partner users recruited from the market's REIA → calibrate deal assumptions with them → public launch.

### 6.3 Wave schedule (solo dev + Claude Code, slice cadence; calendar estimates assume current part-time intensity)

| Wave | Market | New machinery burned in | Estimate | Gate to start |
|---|---|---|---|---|
| **P** | — | B1–B4, B10 | 3–4 wks | Amendment 01 Phases 0–1 shipped |
| **0** | Harrisburg (pilot) | `ExtractClient`, first non-Philly zoning authoring (small code), first RETSL distress mapping, first `data_only` county fringe | 2–3 wks | Phase P green |
| **1** | Pittsburgh | `CkanDatastoreClient`, sales-validation filtering, condemned/dead-end factors, brand decision, owner-name compliance memo | 4–6 wks | Wave 0 parity gate passed |
| **2** | Baltimore | B2 in anger (2248), tax-sale list + calendar, `ground_rent` flag, VBN vacancy, MDLandRec posture | 5–7 wks | Wave 1 launch gate passed (see 6.4) |
| **3** | Detroit | Forced-sale pipeline stages, DLBA acquirability channel, nominal-transfer comp filter | 4–6 wks | Wave 2 launch gate + Detroit delinquency feed located |
| **4** | Milwaukee | MPROP mega-mapping, daily extract scheduling, violations-gap degrade | 4–6 wks | Wave 3 launch gate |
| **5** | Cleveland | Annual-cadence distress labeling, fragmented OH forced-sale mapping | 4–6 wks | Wave 4 launch gate |
| *(6)* | *(Chicago — stretch)* | `SocrataClient`, 10× scale plan | separately gated | ≥2 waves retaining + infra headroom review |

End-to-end: roughly **7–10 months** calendar at current intensity, deliberately serialized — waves share almost no parallelizable work for a solo developer, and each wave's learnings (especially B5 authoring speed) compound.

### 6.4 Launch gates & success metrics (per market)

**Data-parity gate (before any users):** ≥98% of in-scope parcels carry spine + geometry; ≥95% verdict coverage; comps engine returns ≥1 usable comp for ≥60% of vacant parcels (or degrades honestly); distress scores computed for every flagged parcel; the 25-parcel golden set passes; every checklist row either live or explicitly *no data source*.
**Launch gate (before next wave starts):** ≥25 design partners active in week 1; ≥40% of them hit a Pro-cap event in month 1 (the purchase-intent signal from Amendment 01); ≥5 paying conversions or documented willingness-to-pay interviews; saved-search/watchlist creation ≥30% of actives (the retention predictors); zero severity-1 data-accuracy reports open.
**Standing per-market health:** ingest freshness green across sources; verdict staleness < 8 days; alert email CTR tracked per market.

---

## 7. Risks & open questions

1. **Zoning authoring correctness is the program's liability center.** Mitigations are structural (NULL-over-guess, corpus-grounded density, golden-set verification, provisional `code_version` labels) but a wrong by-right number in a new market burns trust fastest. Budget local expert review per market (a zoning attorney or expediter, a few hours) before removing the "provisional" label.
2. **Solo-dev serialization.** Seven-plus months of waves competes with Amendment 01 revenue work and Philadelphia support. The gates exist to make *stopping after any wave* a respectable outcome — Pittsburgh alone nearly doubles TAM in-state.
3. **Upstream ToS/licensing.** WPRDC DUA, Allegheny owner-name ordinance, Maryland Archives AUP, city portal terms — the `docs/data-licenses.md` ledger and the ADR-0026 "compliant by construction" posture govern; no scraping around a paywall or prohibition, ever.
4. **Distress-feed variance** (Detroit ◐, Cleveland annual) directly weakens the flagship leads/alerts loop in those markets — the product must label cadence, and marketing must not promise dailies where the county publishes annuals.
5. **Willingness-to-pay at Detroit/Cleveland price points** — validated at the 25-partner stage before full build; the gate order (Pittsburgh, Baltimore first) front-loads the strongest-economics markets.
6. **Brand** ("PHL" suffix) — decision owed by Wave-1 launch.
7. **Open question:** does Wave 0 (Harrisburg) precede or interleave with Amendment 01 Phase 1? Recommendation: Phase P batches with the ELT work either way; Wave 0 can slot into any two-week gap after that.
8. **Open question:** per-market pricing experiments (cheaper Detroit tier?) — deferred to data from the design-partner cohorts; tiers stay uniform until then.

---

## Appendix A — Wave 0: Harrisburg pilot detail

Scope: **Harrisburg city only** (~25k of Dauphin County's ~117.6k parcels), fed by county data. Dauphin publishes an ArcGIS Hub portal with a **Tax Assessment** category of *periodic extracts* ("tables and GIS datasets... periodic extracts from the Tax Assessment database" — the county's own description) plus a weekly-refresh parcel viewer; there is no query API for assessments, hence `ExtractClient`. PA disclosure applies; sale fields ride the assessment extracts and the Recorder of Deeds (verify depth at kickoff). Distress: Dauphin Tax Claim Bureau operates **RETSL upset/judicial sales** — the first non-MCTLA mapping for ADR-0034, which is precisely the pilot's value. Known gaps to launch degraded: **no open code-enforcement dataset** (violations checklist row = *no data source*), vacancy fully derived, historic/streets layers to verify. Regrid (token on hand) is the sanctioned geometry/ownership fallback if county extracts disappoint. Everything about this wave is deliberately small: it exists to burn in B1–B4, `ExtractClient`, the authoring playbook on a short zoning code, and the `data_only` county-fringe pattern — with a motivated local reviewer for the golden set.

## Appendix B — Evaluated but not selected

**Chicago/Cook (stretch, Wave-6 gated).** The Cook County Assessor's open-data program is the country's best: Parcel Universe (monthly, spatially attached), **Parcel Sales 1999→** with arms-length filter flags and Clerk document numbers, values 1999→, characteristics, permits — all on Socrata with a public SOP repo. City-side violations and zoning layers are equally strong. What defers it is not data but *scale and focus*: ~880k city parcels (1.8M county PINs) triples the estate again, delinquency lives in Treasurer sale lists rather than clean datasets, and the market's competitive noise is highest. Gate: two retained waves + infra review + `SocrataClient`.
**St. Louis (watchlist).** Missouri is a non-disclosure state **except** St. Louis City, St. Louis County, and Jackson County, which mandate certificates of value — and the city's own address search exposes sale prices. So G1 technically passes for the city; what's unverified is a *bulk* sales feed, and the delinquency stack. Strong LRA vacancy story. Re-evaluate after Wave 2 with one day of source spelunking.
**Washington DC (deferred).** Superb portals, but the thesis is distress supply and cheap dirt; DC has neither at scale. Revisit only if the persona broadens beyond distress/infill.
**Camden / Chester / Norristown (metro add-on batch).** Distribution-free adjacencies for the existing Philly REIA audience; individually below the TAM bar. Candidate for a post-Wave-2 mini-batch under the same playbook (NJ MOD-IV statewide assessment data helps Camden).
**County-wide anything.** Fails §2.3 everywhere: Dauphin ~40 zoning ordinances, Allegheny 130.

## Appendix C — Source index (verified during research for this PRD, 2026-07-04)

- WPRDC portal & datasets: `data.wprdc.org` — property assessments (+ Parcel Information Extractor covering assessments, sales, PLI violations, liens), Property Sale Transactions (validation codes), Tax Liens 1995→ (monthly; docket-number caveat), City of Pittsburgh tax delinquency, condemned & dead-end properties, city-owned (eProperties Plus), foreclosures; Property API: `tools.wprdc.org/property-api/`. Allegheny Ordinance 3478-07 noted on the sales dataset page.
- Open Baltimore: `data.baltimorecity.gov` — Real Property Information; **Vacant Building Notices** (daily); **Open Bid List – Vacants to Value**. Context figures (237,403 parcels; ~14.8k VBNs; ~7,905 city-owned derelict lots; 6–10k liens/yr at tax sale): Abell Foundation "The Costs of Baltimore's Vacant Housing" (2022) and BNIA BOLD project.
- Maryland deeds: `mdlandrec.net` / `landrec.msa.maryland.gov` (Maryland Judiciary + State Archives) — free images with free registration; SDAT Real Property search carries per-parcel liber/folio deed references (no owner-name search).
- Detroit: `data.detroitmi.gov` (ArcGIS Hub) — Parcels (Current, per tax year, Assessor), Property Sales, Blight Violations, **DLBA Owned Properties** ("largest property owner in Detroit"), permits, neighborhoods, parcel viewer w/ zoning.
- Milwaukee: `data.milwaukee.gov` (CKAN) — **MPROP** (daily; ~160k records; 90+ fields; exempt/city-owned caveat), Delinquent Real Estate Tax Accounts (monthly; principal-only), sales history incl. vacant land (yearly); `milwaukeemaps.milwaukee.gov/arcgis/rest/services` — parcels w/ MPROP values, tax delinquency, vacant buildings, city-owned inventory, foreclosure status (per UWM GIS guide).
- Cuyahoga/Cleveland: `fiscalhub.gis.cuyahogacounty.gov` (parcels, values, recent sales; CSV/GeoJSON/REST), `data-cuyahoga.opendata.arcgis.com`, county Fiscal Officer pages (annual delinquent list publication; Forfeited Lands Sale).
- Cook/Chicago: `datacatalog.cookcountyil.gov` — Assessor Parcel Universe (monthly), **Assessor Parcel Sales 1999→** (monthly, arms-length filter columns, Clerk doc numbers, 14-digit zero-padded PINs), values, characteristics; `github.com/ccao-data` (SOPs).
- Dauphin/Harrisburg: `data-dauphinco.opendata.arcgis.com` (Tax Assessment category: "periodic extracts... tables and GIS datasets available for download"), `gis.dauphincounty.org` parcel viewer (weekly refresh), ~117,586 county parcels (third-party parcel-data vendors), Regrid coverage confirmed.
- Missouri disclosure carve-out: MOST Policy Initiative science note + reporting on certificates of value in St. Louis City/County and Jackson County; SoldFast/Bezit non-disclosure state lists.

*All upstream data "as is"; field names verified against live APIs during each wave's ingestion slice per standing practice. This PRD supersedes nothing; it sequences after Amendment 01 and will be executed via per-market kickoff ADRs (0029+).*
