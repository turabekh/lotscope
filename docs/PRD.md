# LotScope PHL — Product Requirements Document (Full Vision)

**Working title:** LotScope PHL (placeholder — rebrand at will)
**Document type:** Full-feature PRD (ideal-state, not MVP-scoped)
**Version:** 0.1 · **Date:** 2026-06-27 · **Owner:** Turaboy · **Status:** Draft for refinement

**How to read this:** This is the complete platform vision. Every feature carries a tier tag — Core, Differentiator, Growth, Adjacent — so you can extract an MVP later by filtering, without losing the big picture. Nothing here is pre-cut.

---

## 1. Vision & Thesis

**One line:** The single screen that tells anyone — investor, builder, agent, or owner — what can be built on any Philadelphia vacant lot, what it's worth, and what's wrong with it, with the reasoning shown and the sources cited.

**The wedge.** Philadelphia already publishes the richest property data of any major US city — parcels, assessments, real recorded sale prices, zoning, L&I, demolitions, tax delinquency, the Land Bank, and the city's own vacancy model. The raw data exists; nobody has turned it into an answer. National tools (PRYCD, LandApp, Acres, Land Portal) are a mile wide and an inch deep, built for rural/exurban raw land, and they cannot reason about Philadelphia's zoning code, its by-right envelopes, its liens and sheriff sales, or its Land Bank. LotScope wins by being Philadelphia-deep: a reasoning layer on top of the city's full data stack, plus real comps (which Texas-style non-disclosure markets can't offer), plus an owner-side revenue stream the generic tools ignore.

**Why this can be monetized in Philadelphia specifically.** A hot, active infill market with tens of thousands of vacant parcels; a defined local audience of rowhouse developers, flippers, wholesalers, agents, and CDCs who pay for deal flow and due diligence; a large pool of tax-delinquent and over-assessed parcels that supports an owner-side appeal business; and free, high-quality city data that keeps cost of goods low and margins high.

## 2. Problem Statement

Evaluating a Philadelphia vacant lot today means manually cross-referencing at least seven systems — OPA assessments, DOR recorded transfers, Zoning Base Districts, L&I violations/permits/demolitions, the tax-delinquency dataset, the Land Bank/city-owned inventory, and FEMA flood — then interpreting Title 14 of the zoning code to figure out what can be built by-right. That is hours of work per parcel, it requires expertise most buyers don't have, and a single missed flag (a tangled title, a six-figure tax lien, a lot too narrow to build on by-right) turns into an expensive mistake. There is no tool that does this end-to-end for Philadelphia and returns a plain answer.

**Jobs to be done:**

- Find the vacant lots worth my time, filtered by what matters to me.
- Judge whether a specific lot is a good buy and at what price.
- Understand what I can legally build on it, in plain English.
- Avoid the deal-killers (liens, title, zoning, flood, demolition).
- Act — reach the owner, model the deal, make an offer, manage my pipeline.
- (Owner side) Know what my lot is worth, whether I'm over-assessed, and how to sell or appeal.

## 3. Market & Opportunity (Philadelphia)

- **Active infill market.** Zoning-permit filings have intensified over the past decade; developers are bullish on previously overlooked vacant parcels, pushing up land value.
- **Large addressable inventory.** The city's Vacant Property Indicators model flags tens of thousands of likely-vacant lots citywide — your core inventory, handed to you for free.
- **Real comps.** Unlike non-disclosure states, Philadelphia's DOR publishes recorded sale prices (with realty transfer tax) back to 1999 — making honest valuation possible.
- **Distress supply for the owner-side business.** A routinely-updated tax-delinquency dataset plus sheriff-sale activity supplies both motivated-seller leads and tax-appeal candidates.
- **Low cost of goods.** The bulk of the data is free, open, and API-accessible (Carto + ArcGIS Hub), so gross margin is structurally high.

**TAM framing (Philadelphia).** Paying segments: small/infill developers and builders, flippers/wholesalers, land-focused agents and brokerages, buy-and-hold land investors, CDCs/nonprofits, and lot owners. The single-market ceiling is intentional — go deep, dominate, then port the same engine to other rich-open-data cities (NYC, Chicago, DC, LA) as an expansion play.

## 4. Personas

| Persona | Goal | Key pains | Willingness to pay | Notes |
|---|---|---|---|---|
| **Infill developer / small builder** (primary) | Buy lots, build rowhouses/duplexes/triplexes for profit | By-right envelope, ARV, profit math, zoning/permit risk | High — pays for deal flow + DD + feasibility | The core payer; deepest feature needs |
| **Land flipper / wholesaler** | Buy cheap, assign/resell at volume | Sourcing, owner contact, pricing, off-market lists, mail | High — pays for lead gen + outreach | Volume user; outreach-heavy |
| **Buy-and-hold land investor** | Acquire/hold lots for appreciation, side yards | Valuation, lien/tax checks, portfolio tracking | Medium | Long-tail, sticky |
| **Individual / owner-occupant buyer** | Buy adjacent lot, build a home, garden | "Can I do X here," value, process | Low subscription; per-report or freemium | High volume, low LTV; transactional monetization |
| **Real estate agent / broker** | Serve land buyers/sellers, farm a neighborhood | Client-ready reports, listing intel, comps | Medium-high (pro/white-label) | White-label channel |
| **CDC / nonprofit / community group** | Neighborhood development, anti-blight, land banking | Vacancy, ownership, disposition data | Low (civic tier) | Credibility + partnership channel |
| **Lot owner / over-assessed owner** | Sell, appeal taxes, understand value | Don't know value, over-paying taxes, tangled title | Contingency or flat fee | Powers the Adjacent revenue lines |

## 5. Feature Catalog (Full Set)

**Tier legend:** Core = the spine; Differentiator = what wins; Growth = scale/monetization; Adjacent = separate but synergistic bets.

### 5.1 Map, Search & Discovery

| Feature | Description & user value | Tier |
|---|---|---|
| Interactive vector parcel map | Fast pan/zoom map of every Philadelphia parcel; the front door. | Core |
| Vacant-lot layer & color-by | Toggle vacant lots; color by zoning, value, buildability, vacancy confidence, or opportunity score. | Core |
| Multi-criteria filters | Filter by size, dimensions, zoning, est. value, by-right units, owner type, vacancy, flood, lien status, neighborhood, council district, etc. | Core |
| Draw / radius / neighborhood search | Search within a drawn polygon, radius, or named neighborhood/RCO. | Core |
| Universal search | Address, parcel number, or owner search (Elasticsearch-backed). | Core |
| Saved searches + alerts | Save criteria; get email/push alerts when new matching lots appear. | Differentiator |
| Map data layers | Zoning, flood, historic districts, opportunity zones, council districts, neighborhoods, RCO boundaries, transit, schools, crime. | Core |
| Imagery | Aerial/satellite + Street View + historic aerials (GeoHistory) for change-over-time. | Core |
| Heat overlays | Permit activity, sales velocity, investor demand, vacancy density. | Growth |
| Parcel compare | Side-by-side comparison of multiple lots. | Differentiator |

### 5.2 Parcel Dossier / Intelligence

| Feature | Description & user value | Tier |
|---|---|---|
| Full parcel profile | Address, parcel #, owner, mailing address, dimensions, area, zoning, land use, assessment & sale history in one panel. | Core |
| Ownership detail + owner portfolio | Current owner plus all other parcels they own (assemblage / motivated-seller signal). | Differentiator |
| Assessment & tax history | OPA market/land/building values over time. | Core |
| Transfer history | DOR recorded sales/deeds/mortgages/sheriff deeds with prices. | Core |
| AI plain-language summary | One-paragraph plain-English read of the parcel. | Differentiator |
| Lot-condition from imagery (CV) | Computer vision on aerials: cleared / overgrown / debris / has structure. | Differentiator |
| Adjacent parcels & assemblage | Flag neighboring lots and consolidation opportunities. | Growth |
| Utilities proximity | Water/sewer/electric/gas availability indicators. | Differentiator |
| Neighborhood context | Median values, recent sales, permits, demographics around the lot. | Growth |

### 5.3 Developability / Buildability Engine (Philadelphia core brain)

| Feature | Description & user value | Tier |
|---|---|---|
| Zoning resolution + overlays | Resolve each lot's base district (RSA/RM/CMX/etc.) and overlays (historic, NCO, /CTR). | Core |
| By-right use determination | What's allowed without a variance: single-/two-/multi-family, commercial, mixed-use. | Differentiator |
| By-right dimensional analysis | Compare lot area/width to district minimums → conforming vs. non-conforming. | Differentiator |
| Buildable envelope | Max by-right units, height, occupied/open area, setbacks, required parking. | Differentiator |
| Variance / ZBA likelihood | Flag when a desired use/size needs a variance or special exception. | Differentiator |
| Build-scenario modeling | "1 unit vs 3 units" feasibility with by-right vs. variance paths. | Differentiator |
| Subdivision / consolidation potential | Whether the lot can be split or merged for a better outcome. | Growth |
| Overlay & RCO impacts | Historic review, neighborhood conservation, required community notification. | Growth |
| Buildable-area calc | Net buildable area after flood, setbacks, easements. | Differentiator |
| Buildability score + reasons | A single score with the make-or-break reasons shown. | Core |

Dimensional standards are populated from Title 14 of the Philadelphia Code into a versioned lookup table — never hardcoded blindly, since the code is amendable.

### 5.4 Valuation & Deal Analysis

| Feature | Description & user value | Tier |
|---|---|---|
| Land value estimate (AVM) | Comp-based estimate with a confidence score. | Differentiator |
| Comparable sales finder | Real recorded (RTT) comps, filterable, mapped. | Core |
| ARV / finished-product estimate | Value of the completed build for a given scenario. | Differentiator |
| Deal score / underpriced flag | Flag lots priced below the model — "deal radar." | Differentiator |
| Feasibility / profit calculator | Acquisition + construction + soft costs + sale → margin / ROI. | Differentiator |
| Max allowable offer (MAO) | Back-solve the offer that hits a target margin. | Growth |
| Hold / build-to-rent modeling | Rent and hold scenarios for buy-and-hold users. | Growth |
| Assessment-vs-market gap | Over/under-assessment signal (feeds the tax-appeal product). | Differentiator |
| Scenario comparison | Compare multiple deal structures on one parcel. | Growth |

### 5.5 Risk & Due Diligence

| Feature | Description & user value | Tier |
|---|---|---|
| Tax delinquency / lien check | Amount, years owed, sheriff-sale exposure. | Core |
| City / Land Bank / PHDC ownership | Flag publicly-owned lots and disposition status. | Core |
| L&I status | Violations, permits, demolitions, unsafe/imminently-dangerous flags. | Core |
| Title red flags | Multiple/deceased owners, tangled title, conservatorship signals. | Differentiator |
| Flood & environmental | FEMA flood zone, contaminated sites / brownfields proximity. | Core |
| Access / easements | Easements, rights-of-way, landlocked detection. | Differentiator |
| Conservatorship / Act 135 candidates | Distressed-property legal pathways. | Adjacent |
| Sheriff / tax sale calendar | Upcoming sales and parcel status. | Growth |
| Auto due-diligence checklist | Per-parcel checklist auto-populated from the data. | Differentiator |
| Risk score + flag list | Consolidated risk read with every flag itemized. | Core |

### 5.6 AI Assistant — "Ask the Parcel" (flagship differentiator)

| Feature | Description & user value | Tier |
|---|---|---|
| Grounded natural-language Q&A | "Can I build a triplex? Do I need a variance? Is this in the Land Bank?" — answered from zoning code + parcel data, with citations. | Differentiator |
| Deed / restriction extraction | RAG/OCR over recorded deeds & plats to surface restrictions ("no multi-family," easements). | Differentiator |
| Zoning code interpretation | Per-parcel reading of Title 14 with the specific section cited. | Differentiator |
| Process guidance | What permits/steps are needed to build X (ZBA, RCO, L&I). | Differentiator |
| Document summarization | Summarize deeds, plats, zoning notices in plain English. | Growth |
| Cross-parcel Q&A | Ask questions across a saved set ("which of these allows 3 units?"). | Growth |
| AI report drafting | Generate narrative sections of dossiers and investor reports. | Growth |

**Guardrail:** every AI answer is framed as informational (not legal advice), shows confidence, and cites the source section/document.

### 5.7 Sourcing & Outreach

| Feature | Description & user value | Tier |
|---|---|---|
| Off-market lead lists | Build lists like "vacant + delinquent + absentee owner." | Growth |
| Owner skip-trace | Append phone/email via provider. | Growth |
| Direct mail campaigns | Postcards/letters with templates and response tracking. | Growth |
| SMS / email sequences | Outreach automation to owners. | Growth |
| Absentee / out-of-state targeting | Filter for owners likely to sell. | Growth |
| Motivated-seller scoring | Score by delinquency + vacancy + absentee + ownership age. | Differentiator |
| Land Bank acquisition workflow | Eligibility, side-yard / EOI, application tracking. | Adjacent |
| Sheriff / tax sale lead tracking | Track and act on auction pipelines. | Growth |
| Lead status & response tracking | Manage outreach outcomes. | Growth |

### 5.8 Market Intelligence & Analytics

| Feature | Description & user value | Tier |
|---|---|---|
| Neighborhood dashboards | Values, sales velocity, permits, vacancy trends per area. | Growth |
| Price & rent trend charts | By neighborhood / zip / zoning. | Growth |
| Development-activity heatmaps | Where permits are filed and developers are buying. | Growth |
| Comp trend analytics | How land comps move over time. | Growth |
| Incentive overlays | Opportunity zones, tax abatements, special districts. | Growth |
| Investor-activity intel | Who is buying, and where. | Growth |
| Vacancy & blight trend tracking | Track change at neighborhood level. | Growth |
| Custom market reports | Generate area reports on demand. | Growth |

### 5.9 Portfolio, Pipeline & Collaboration

| Feature | Description & user value | Tier |
|---|---|---|
| Watchlists | Save parcels with tags and notes. | Core |
| Deal pipeline | Kanban: lead → DD → offer → under contract → closed. | Growth |
| CRM-lite | Track contacts, owners, sellers. | Growth |
| Per-deal document management | Store docs against each deal (S3). | Growth |
| Notes, tasks, reminders | Lightweight productivity per parcel/deal. | Growth |
| Team collaboration | Shared lists, comments, assignment. | Growth |
| Price/status monitoring | Auto-alerts on changes to saved lots. | Differentiator |
| Activity history / audit | Track what changed and when. | Growth |

### 5.10 Reports & Export

| Feature | Description & user value | Tier |
|---|---|---|
| One-click PDF dossier | Branded full parcel report. | Differentiator |
| Investor / lender / partner report | Decision-ready package to share. | Growth |
| Comp report | Standalone valuation comps. | Growth |
| Feasibility / pro-forma report | The deal math, exportable. | Growth |
| Shareable web links | Send a live parcel view. | Growth |
| CSV / Excel export | Bulk data out. | Growth |
| White-label / co-branded reports | Agent/brokerage branding. | Growth |
| Scheduled / auto reports | Recurring deliverables. | Growth |

### 5.11 Workflow & Transaction Tools

| Feature | Description & user value | Tier |
|---|---|---|
| Offer / LOI generation | Auto-draft offers from parcel data. | Growth |
| Purchase agreement templates | PA/Philadelphia-appropriate templates. | Growth |
| E-signature integration | Sign without leaving the platform. | Growth |
| DD checklist & tracking | Run due diligence to close. | Growth |
| Title / closing handoff | Integrate or hand off to a title company. | Growth |
| Document vault | Secure per-transaction storage. | Growth |
| Transaction timeline | Track milestones to closing. | Growth |

### 5.12 Owner-Side & Tax Appeal (Adjacent — same data, different customer)

| Feature | Description & user value | Tier |
|---|---|---|
| Over-assessment scoring | Rank parcels assessed above model/comps. | Adjacent |
| Tax-appeal eligibility + savings estimate | Show likely savings before filing. | Adjacent |
| Appeal assistance / filing support | First Level Review / BRT appeal workflow. | Adjacent |
| "Sell my vacant lot" | Owner valuation + buyer matching / lead gen. | Adjacent |
| Owner dashboard | My parcels, taxes, value, inbound offers. | Adjacent |
| Owner outreach (compliance/sell) | Reach owners of nuisance/vacant lots. | Adjacent |

### 5.13 Marketplace & Lead Gen (Growth — network effects)

| Feature | Description & user value | Tier |
|---|---|---|
| Off-market listing/marketplace | Owners list lots; buyers browse. | Growth |
| Buyer–seller matching | Match motivated owners to active buyers. | Growth |
| Lead marketplace | Sell qualified motivated-owner leads (referral/take-rate). | Adjacent |
| Featured listings | Paid promotion. | Growth |
| Agent directory | Connect users to land-savvy agents. | Growth |

### 5.14 Accounts, Teams, Billing & Admin

| Feature | Description & user value | Tier |
|---|---|---|
| Auth & roles | Email/SSO, role-based permissions. | Core |
| Subscriptions & billing | Tiered plans (Stripe), proration, invoices. | Core |
| Usage metering / credits | Meter skip-trace, mail, report credits. | Growth |
| Team seats & management | Add/manage seats and roles. | Growth |
| Tier limits | Enforce feature/usage caps per plan. | Core |
| Admin console | Data status, user/content management. | Core |
| API keys & developer portal | For the API/data tier. | Growth |
| White-label config | Brokerage/agent branding. | Growth |

### 5.15 Data Platform & Infrastructure (the moat, treated as product)

| Feature | Description & user value | Tier |
|---|---|---|
| Ingestion pipelines | Scheduled ETL from Carto SQL, ArcGIS Hub, FEMA, Regrid, deeds. | Core |
| Freshness monitoring + transparency | SLAs and visible "last updated" per dataset. | Core |
| Parcel-key reconciliation | Resolve OPA ↔ PWD ↔ RTT identity mismatches. | Core |
| Verdict computation engine | Batch + on-demand computation of the parcel verdict. | Core |
| Vector tile serving | Self-hosted tiles (Martin/pg_tileserv) for cost control. | Core |
| Search index | Elasticsearch for address/owner/parcel search. | Core |
| Document store + OCR | S3 + OCR pipeline for deeds/plats feeding RAG. | Differentiator |
| Data-quality & confidence scoring | Per-field quality and confidence surfaced to users. | Differentiator |
| Verdict versioning / audit | Reproducible, auditable verdicts. | Growth |

### 5.16 Notifications & Engagement

| Feature | Description & user value | Tier |
|---|---|---|
| New-match alerts | Saved-search hits. | Differentiator |
| Watchlist change alerts | Price/status changes on saved lots. | Differentiator |
| Disposition alerts | New sheriff-sale / Land Bank lots in target area. | Growth |
| Permit-nearby alerts | Development signal near saved lots. | Growth |
| Digest emails | Weekly opportunity digest. | Growth |
| In-app + push | Real-time engagement (mobile). | Growth |

### 5.17 Mobile & Field Tools

| Feature | Description & user value | Tier |
|---|---|---|
| Mobile app / PWA | LotScope on the go. | Growth |
| "Lots near me" | Geolocated discovery. | Growth |
| Drive-for-dollars | Log lots from the field. | Growth |
| Geotagged photos | Attach field photos to parcels. | Growth |
| Offline saved parcels | Access without signal. | Growth |
| On-the-go verdict | Quick verdict in the field. | Growth |

### 5.18 Trust, Compliance & Legal (cross-cutting)

| Feature | Description & user value | Tier |
|---|---|---|
| Source citations everywhere | Every data point and AI answer cites its source. | Core |
| Confidence indicators | Show certainty, never false precision. | Core |
| "Not legal/financial advice" framing | Clear disclaimers throughout. | Core |
| Data-license compliance | Honor city "as-is" terms, Regrid, provider licenses. | Core |
| Outreach compliance | TCPA / DNC / CAN-SPAM for mail/SMS/email. | Growth |
| Fair Housing compliance | Guardrails on targeting/marketing. | Growth |
| PII security & access control | Protect owner contact data. | Core |
| Audit trail | Record verdicts and actions. | Growth |

## 6. Flagship Spec — The "Parcel Verdict"

The product's soul is one screen. When a user clicks any vacant lot:

1. **Headline verdict** — a single buildability/opportunity score with a one-line plain-English summary.
2. **What you can build** — by-right use(s), max units, height, and whether a variance is needed; a 1-line "buildable envelope" plus alternate scenarios.
3. **What it's worth** — a confidence-scored value range, the top comps (mapped), and the assessment-vs-market gap.
4. **What's wrong with it** — itemized red flags: liens/delinquency, title issues, L&I/demolition, Land Bank ownership, flood, access.
5. **Ask the parcel** — an inline Q&A box for plain-English questions, answered with citations.
6. **Act** — save to watchlist, generate PDF, model the deal, or reach the owner.

Every element shows its source and last-updated date. The verdict is the free hook in limited form; the full verdict + Q&A + reports sit behind the paywall.

## 7. AI / ML Components

- **RAG Q&A engine** — retrieval over (a) Title 14 zoning code text, (b) the parcel's resolved district + dimensions, (c) recorded deeds/plats; generation grounded and cited (Claude API + vector store).
- **Document understanding** — OCR + extraction of restrictions, easements, and conditions from recorded documents.
- **Valuation model** — comp-based AVM trained on RTT recorded sales, with confidence/coefficient-of-variation handling for thin sub-markets.
- **Vacancy refinement** — improve on the city's Vacant Property Indicators with imagery and assessment signals.
- **Lot-condition CV** — classify aerial imagery (cleared / overgrown / debris / structure present).
- **Motivated-seller / over-assessment scoring** — ranking models over delinquency, vacancy, absentee, ownership tenure, and assessment-vs-comp gap.

## 8. Data Sources & Data Model (summary)

**Tabular via Carto SQL** (`https://phl.carto.com/api/v2/sql`): `opa_properties_public` (assessments/owner/value), `pwd_parcels` (parcel polygons), `rtt_summary` (recorded transfers/comps), real estate tax delinquencies, L&I violations/permits/demolitions.

**GIS via ArcGIS Hub** (`data-phl.opendata.arcgis.com`): Vacant Indicators – Land, Zoning Base Districts, building footprints, land use, FEMA flood, historic districts, council districts, neighborhoods/RCOs.

**Publicly-owned / Land Bank inventory:** city-owned property dataset (locate current source).

**Recorded documents:** DOR records system for deed/plat images (RAG layer).

**Third-party (optional):** Regrid (standardized ownership + mailing for skip-trace; portability beyond Philadelphia), skip-trace provider, imagery provider.

**Data-model spine:** a master `parcel` table keyed on OPA `parcel_number`, with related `zoning_district`/`zoning_standard`, `sale`, `tax_status`, `li_event`, and a computed `parcel_verdict` materialized view. Store geometry in EPSG:2272 (analysis) and 4326 (tiles).

**Known gotchas:** Carto times out on full-table dumps (chunk by parcel ranges); OPA/PWD/RTT join keys need reconciliation; case-sensitive SQL (use `ILIKE`).

## 9. Monetization & Pricing

Multiple revenue lines; the generic competitors' floor (PRYCD ≈ $25/mo, LandApp ≈ $6/mo) means don't compete on raw data price — charge a premium justified by Philadelphia depth, the answer layer, and workflow, and capture revenue the generic tools can't (pro/agency, owner-side, marketplace).

| Stream | Model | Indicative price | Target |
|---|---|---|---|
| Free | Freemium hook | $0 | Vacant-lot map, basic parcel info, a few verdicts/mo |
| Pro | Subscription | ~$49–99/mo | Unlimited verdicts, comps, AI Q&A, watchlist, alerts, reports — individual investors/flippers |
| Team / Agency | Subscription + seats | ~$199–399/mo | Pipeline/CRM, outreach, advanced analytics, white-label — developers, brokerages |
| Enterprise / Data / API | Custom | Custom | Data feed, API, integrations — institutions, lenders, CDCs, the city ecosystem |
| À la carte | Transactional credits | Report ~$10–25; skip-trace & mail credits | Occasional/retail buyers; outreach-heavy users |
| Owner-side: tax appeal | Contingency or flat fee | % of first-year savings, or flat | Over-assessed lot owners |
| Owner-side: sell my lot | Lead gen / referral | Per-lead or take-rate | Motivated owners → investors/agents |
| Marketplace | Listing fee / take-rate | % or flat | Facilitated transactions (later) |

## 10. Go-to-Market (Philadelphia)

- **Top of funnel:** the free, genuinely-useful vacant-lot map — the best free Philadelphia lot explorer in existence — plus Philadelphia-specific content/SEO ("can I build a duplex on [zoning] in Philly?").
- **Community:** local REIAs, Philadelphia developer/investor groups, wholesaler networks, and meetups; dogfood and credibility via your own lot.
- **Partnerships:** title companies, land-savvy agents/brokerages (white-label), CDCs and the Land Bank ecosystem (civic tier + credibility), and lenders.
- **Owner-side acquisition:** direct outreach to delinquent/over-assessed owners (the tax-appeal funnel doubles as a seller funnel).
- **Expansion later:** replicate to other rich-open-data cities once Philadelphia is dominated.

## 11. Competitive Landscape & Differentiation

| Competitor | What they do | Why LotScope wins in Philadelphia |
|---|---|---|
| PRYCD | Land valuation, skip-trace, mail (rural-focused, US-wide, ~$25/mo) | No Philadelphia zoning reasoning, no by-right answer, weak in urban infill |
| LandApp / LandGate | 40+ national layers, energy-focused (~$6/mo) | Energy/rural lens; no Title 14 interpretation, liens, Land Bank, or local comps |
| Acres.com | Due-diligence panel + portfolio | National breadth, not Philadelphia depth or owner-side |
| Pebble | Land-investor CRM | CRM only; no intelligence/answer layer |
| Land Portal | Map + AI vacant filter + filters | Rural raw-land orientation; no urban-infill reasoning |
| Zoneomics | National zoning data | Data layer, not a Philadelphia answer/workflow product |
| PropStream | General REI data (160M props) | Houses-first, generic; no land/infill or by-right modeling |
| Land.com / Zillow | Listings | Listings only; no off-market, no analysis, no DD |

**Moat:** Philadelphia data depth + the reasoning/answer layer + real recorded comps + integrated risk (liens/title/L&I/Land Bank) + owner-side revenue — a combination none of the above has in this market.

## 12. Non-Functional Requirements

- **Performance:** sub-second map pan/zoom; vector tiles served from own infra; verdict render < ~2s.
- **Freshness:** scheduled ingestion with visible "last updated"; daily for L&I/demolitions, regular for assessments/transfers/delinquency.
- **Accuracy & honesty:** confidence scores everywhere; no false precision; show the data and let users verify.
- **Scalability:** handle ~580k citywide parcels and tens of thousands of vacant lots; batch verdict recompute.
- **Security & privacy:** protect owner PII and skip-trace data; role-based access; encryption at rest/in transit.
- **Reliability:** graceful handling of upstream (Carto/ArcGIS) outages; cached layers.
- **Accessibility & mobile:** responsive/PWA; WCAG-minded UI.

## 13. Legal, Compliance & Trust

- **AI = informational, not legal advice.** Cite the code section/document, show confidence, recommend confirming with L&I/zoning/an attorney. Get counsel on UPL exposure and disclaimers/ToS.
- **Data licensing.** City data is "as-is / hold-harmless"; honor those terms and Regrid/provider licenses; disclaim accordingly.
- **Outreach compliance.** TCPA/DNC for SMS/calls, CAN-SPAM for email, mail-list hygiene.
- **Fair Housing.** Guardrails on any targeting/marketing copy.
- **Auditability.** Reproducible verdicts and an action audit trail.

## 14. Technical Architecture (high-level)

- **Data core:** PostGIS (parcels, layers, verdicts), Elasticsearch (search), S3 (documents/imagery), vector store (RAG).
- **Backend:** Python / FastAPI; verdict engine (batch + on-demand); ingestion ETL (Airflow or scheduled jobs) from Carto SQL + ArcGIS Hub + FEMA + Regrid + DOR.
- **AI services:** Claude API for Q&A/summaries; OCR + extraction pipeline; valuation & scoring models.
- **Frontend:** Quasar + MapLibre GL JS; self-hosted tiles (Martin/pg_tileserv).
- **Integrations:** Stripe (billing), skip-trace provider, mail house, e-sign, title/closing, imagery.
- **Infra:** AWS, Docker.

## 15. Success Metrics (KPIs)

- **Acquisition/activation:** signups; first verdict viewed; first parcel saved.
- **Engagement:** WAU/MAU; verdicts/user; searches/user; reports generated.
- **Conversion/retention:** free→paid rate; churn; ARPU; MRR/ARR.
- **Product quality:** data coverage % and freshness lag; verdict accuracy validated against subsequent permits/sales; AI answer correctness; NPS.
- **Owner-side:** appeals filed; savings delivered; sell-side leads converted.

## 16. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Data freshness/maintenance burden | Lean on city APIs + Regrid; freshness monitoring; visible "last updated." |
| Accuracy & legal liability (UPL) | Cite sources, show confidence, disclaim, get counsel. |
| Competitive/price pressure & commoditization | Compete on Philadelphia depth + answers + workflow + owner-side, not raw data price. |
| Single-market TAM ceiling | Intentional; expansion path to other rich-open-data cities. |
| Distribution risk | Community-led GTM; free map hook; partnerships. |
| Upstream data-access changes (city) | Abstract ingestion; cache; Regrid as fallback for base parcels. |
| Third-party dependency (skip-trace, imagery) | Provider-agnostic interfaces. |

## 17. Suggested Phasing (for later MVP extraction)

Full set above is the vision; a natural build order:

- **Phase 1 — Foundation (Core):** map + parcel dossier + developability engine + risk flags + basic valuation + the Parcel Verdict + free tier.
- **Phase 2 — Differentiation & monetization (Differentiator):** AI "Ask the Parcel," full comps/AVM, deal scoring, reports, watchlist/alerts, Pro billing.
- **Phase 3 — Pros & scale (Growth):** pipeline/CRM, outreach/skip-trace, team/agency tier, white-label, market analytics, mobile/field.
- **Phase 4 — Adjacent & network (Adjacent/Growth):** owner-side tax appeal, sell-my-lot lead gen, data/API, marketplace, multi-market expansion.

## 18. Open Decisions

1. **Lead persona** — infill developer vs flipper vs owner-side first?
2. **Buyer-side vs owner-side sequencing** — which revenue line proves out first?
3. **Build vs license non-city data** (Regrid now or later)?
4. **Free-tier generosity** — how much verdict to give away for the hook?
5. **AI advice posture** — how conservative on the legal-interpretation feature?
6. **Partnership strategy** — city/CDC/title/agent — which first?
7. **Expansion timing & target cities.**

## Appendix A — Glossary (Philadelphia)

- **OPA** — Office of Property Assessment (assessments; `opa_properties_public`).
- **RTT** — Realty Transfer Tax / DOR recorded transfers (`rtt_summary`; the comp source).
- **L&I** — Licenses & Inspections (violations, permits, demolitions).
- **PWD parcels** — authoritative parcel polygons.
- **Vacant Property Indicators** — the city's per-parcel vacancy model.
- **Land Bank / PHDC** — public land-holding/disposition entities.
- **RSA / RM / CMX** — Residential Single-family Attached / Residential Multi-family / Commercial Mixed-use zoning districts (Title 14).
- **ZBA** — Zoning Board of Adjustment (variances/special exceptions).
- **RCO** — Registered Community Organization (zoning notification).
- **Sheriff sale** — public auction of tax-/mortgage-foreclosed property.
- **Act 135** — Pennsylvania conservatorship statute for blighted property.

---

*End of PRD v0.1 — refine and extract MVP from here.*

*Converted from `docs/LotScope-PHL-Full-PRD.md.pdf` (added in `962d8e6`, removed in `da696ce`) with no changes to the substance. Where the text has since been superseded by an ADR — notably Elasticsearch in §5.1, §5.15 and §14, dropped for Postgres search in ADR-0005 — the original wording is preserved and the ADR governs. Later scope changes live in `PRD-amendment-01-monetization.md` and `PRD-amendment-02-geographic-expansion.md`.*
