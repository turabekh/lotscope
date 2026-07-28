# PRD Amendment 03 — Commercial Launch Readiness and Infill Developer Focus

**Status:** Proposed for owner approval  
**Date:** 2026-07-28  
**Owner:** Turaboy  
**Amends:** `docs/PRD.md`  
**Related:** `docs/PRD-amendment-01-monetization.md`, `docs/PRD-amendment-02-geographic-expansion.md`, `docs/design/ia-and-layout.md`, `CLAUDE.md`  
**Target:** Philadelphia controlled paid beta, followed by a gated public launch  
**Document role:** This amendment controls launch priority. It does not erase completed functionality or reverse sound architecture.

---

## 0. Amendment authority and precedence

This amendment converts LotScope from a broad feature-complete platform into a focused, commercially testable launch product.

Until the public-launch gates in this document are satisfied:

1. Philadelphia is the flagship commercial market.
2. Existing pilot markets may remain available to invited testers but must not drive launch scope.
3. Launch-readiness work takes priority over geographic expansion, adjacent products, and new broad feature development.
4. Features that do not support the primary acquisition journey may remain in the codebase but should be hidden, secondary, or clearly marked as beta.
5. When this amendment conflicts with older persona, pricing, navigation, or sequencing language, this amendment governs the launch phase.
6. Existing architecture decisions remain authoritative unless this amendment explicitly requires a new ADR.
7. No verdict-contract, scoring, billing, data-model, authentication, or information-architecture change may be made silently. Use an ADR where required by `CLAUDE.md`.

This amendment is complete only when the launch gates are measured with real users and real Philadelphia parcels.

---

## 1. Executive product decision

### 1.1 Launch product

LotScope launches as:

> **The acquisition underwriting platform for small Philadelphia infill developers and land investors.**

### 1.2 Launch promise

> **Find buildable infill opportunities, understand what could kill the deal, and calculate what you can afford to offer before spending days on manual due diligence.**

### 1.3 Core customer decision

LotScope must help the customer answer:

1. Is this parcel worth investigating?
2. What development program appears feasible?
3. Which assumptions support that result?
4. What material risks or unknowns remain?
5. What is the parcel worth under my business assumptions?
6. What should I do next?

### 1.4 Product identity

LotScope is not launched as:

- a generic nationwide property-data platform;
- a generic skip-tracing product;
- a standalone CRM;
- an AI chatbot;
- a tax-appeal marketplace;
- a sheriff-sale directory;
- a broad direct-mail system;
- a replacement for architects, surveyors, attorneys, appraisers, title companies, or municipal approvals.

Those capabilities may support the acquisition workflow, but they are not the launch identity.

---

## 2. Target customer

### 2.1 Primary ideal customer profile

A small or midsized Philadelphia infill developer, land investor, or acquisitions operator who:

- evaluates at least 5–20 acquisition candidates per month;
- buys vacant lots, teardown properties, small multifamily sites, mixed-use sites, or small assemblages;
- generally develops 1–20 units per project;
- performs preliminary underwriting personally or with a small team;
- checks zoning, parcel geometry, recorded sales, ownership, taxes, violations, overlays, and title-related risks manually;
- loses meaningful time or money when early screening is wrong;
- can justify professional software through one avoided bad acquisition or one additional viable deal.

### 2.2 Secondary customers

Secondary customers may be supported after the primary workflow is proven:

- land-focused brokers and agents;
- acquisition managers;
- small development funds;
- wholesalers specializing in lots;
- zoning consultants and architects;
- hard-money lenders reviewing infill deals;
- title and closing partners;
- community development organizations.

### 2.3 Excluded launch personas

Do not optimize the launch experience for:

- casual homeowners;
- general residential agents;
- nationwide institutional users;
- rural land investors;
- consumers seeking final legal or zoning conclusions;
- users whose main need is bulk cold outreach rather than acquisition underwriting.

---

## 3. Jobs to be done

### JTBD-1 — Find viable acquisition candidates

When I define my geography, product type, economics, and risk tolerance, show me parcels that plausibly match my buy box so I do not manually inspect hundreds of irrelevant properties.

### JTBD-2 — Screen a parcel quickly

When I open a parcel, give me a useful preliminary pursue/investigate/pass result in approximately 30 seconds.

### JTBD-3 — Understand buildability

When I inspect a candidate, show the likely program, the exact rules and assumptions used, what passed, what failed, what was estimated, and what was not evaluated.

### JTBD-4 — Underwrite the acquisition

When I enter my development assumptions, calculate project economics, maximum allowable offer, downside exposure, and sensitivity to the largest variables.

### JTBD-5 — Identify deal killers

When material risks, missing data, or professional checks remain, make them impossible to overlook and convert them into a due-diligence checklist.

### JTBD-6 — Act and follow through

When a parcel is worth pursuing, let me save it, add it to the pipeline, assign a next action, obtain permitted contact data, prepare a report or offer, and track the outcome.

---

## 4. Launch user journey

The primary launch journey is:

> **Define buy box → view matched opportunities → open Parcel Verdict → inspect likely program → inspect risks and unknowns → adjust underwriting assumptions → save to pipeline → take next action.**

Every launch feature must improve at least one step in this journey.

### 4.1 Required first-session journey

A new user must be able to:

1. register;
2. choose property types;
3. select Philadelphia areas;
4. enter basic acquisition criteria;
5. receive real matching parcels;
6. open one complete Parcel Verdict;
7. change at least one underwriting assumption;
8. save or add the parcel to the pipeline;
9. create an alert or saved search.

### 4.2 Activation event

A user is activated when, during the first session, the user:

- views a complete Parcel Verdict; and
- saves the parcel or adds it to the pipeline.

Registration alone is not activation.

---

## 5. Scope control

### 5.1 In scope before broad public launch

- Philadelphia data quality and market truth;
- decision-first Parcel Verdict;
- field-level trust, source, and freshness;
- transparent buildability checks;
- editable underwriting and scenarios;
- simplified acquisition navigation;
- buy-box onboarding;
- saved parcels, saved searches, alerts, and pipeline;
- billing, email, support, analytics, and error monitoring;
- backups, restore testing, CI protection, and critical end-to-end flows;
- paid-beta feedback and correction workflow.

### 5.2 Explicitly deferred

Do not start or expand the following until launch gates pass:

- another city or county;
- nationwide coverage;
- native mobile applications;
- public API;
- marketplace functionality;
- owner-side growth campaigns;
- major tax-appeal expansion;
- general-purpose AI features;
- broad direct-mail automation;
- advanced white labeling;
- enterprise SSO;
- large-team administration beyond what a paid beta requires;
- speculative scoring models without validated customer evidence;
- unrelated refactors.

Completed features may remain available when stable, but they do not receive launch priority.

---

## 6. Product principles

### 6.1 Decision before data

The first screen must provide a screening decision and explain it. Raw records and detailed evidence remain available below.

### 6.2 Truth before confidence theater

When the system does not know, it must say so. Missing data must never be presented as a clean result.

### 6.3 Preliminary screening, not final determination

Buildability, valuation, risk, and financial outputs are informational preliminary analyses. The product must clearly identify professional and municipal verification steps.

### 6.4 User assumptions must be visible

No important financial result may appear as a black box. Defaults, source assumptions, user overrides, and formulas must be inspectable.

### 6.5 Provenance at the point of use

Source, effective date, freshness, calculation time, and limitations must appear near the result they qualify.

### 6.6 Narrow launch, deep quality

Philadelphia depth and accuracy are more important than the number of markets or modules.

### 6.7 Corrections become product intelligence

Users must be able to report questionable data or conclusions. Corrections must preserve the parcel, verdict version, source state, and user evidence.

---

## 7. Parcel Verdict launch requirements

### LR-V001 — Screening recommendation

The top of the dossier must show one of:

- Strong candidate
- Worth investigating
- High entitlement risk
- Economics currently unattractive
- Insufficient data
- Likely pass

The label is preliminary screening, not investment advice.

**Acceptance criteria**

- The label is based on explicit deterministic inputs.
- The reason is visible in one sentence.
- Missing critical data can force `Insufficient data`.
- The result is versioned and reproducible.
- A change to the underlying decision contract requires an ADR and verdict-version review.

### LR-V002 — Likely development program

Show a plain-language summary such as:

> Likely base-district program: one attached dwelling, up to three stories, with an estimated gross building area of 1,750 square feet.

**Acceptance criteria**

- Distinguish verified district rules from calculated geometry and assumptions.
- Use conditional language where overlays, lot shape, access, parking, utilities, title, or other rules are not fully evaluated.
- Cite the standards and source version.
- Show master-plan or special-district restrictions prominently.

### LR-V003 — Financial headline

Show:

- acquisition price or asking price when available;
- estimated land value;
- maximum allowable offer;
- total project cost;
- estimated exit value;
- projected profit;
- projected margin;
- confidence or scenario state.

**Acceptance criteria**

- Every figure identifies default, source-derived, calculated, or user-overridden inputs.
- The user can navigate directly to the assumptions.
- Unknown values do not silently become zero.

### LR-V004 — Top deal killers

Show no more than three top issues in the hero, ordered by severity and decision impact.

Examples:

- lot width appears nonconforming;
- street access uncertain;
- master plan required;
- tax delinquency;
- public ownership;
- flood exposure;
- historic controls;
- inadequate comparable-sales evidence;
- title or deed restrictions not evaluated.

All remaining issues appear in the detailed risk section.

### LR-V005 — Required next checks

Generate a deterministic due-diligence checklist based on known gaps and flags.

Examples:

- verify zoning interpretation with the city or a qualified professional;
- order a boundary survey;
- obtain a title report;
- verify utility availability and laterals;
- inspect environmental and geotechnical conditions;
- confirm demolition and historic approvals;
- confirm taxes and municipal balances;
- validate finished-value assumptions.

The checklist must never imply that completing only these items guarantees approval or feasibility.

---

## 8. Trust and evidence requirements

### 8.1 Field-state taxonomy

Every material output must expose one of four states:

| State | Meaning |
|---|---|
| Verified | Directly reported by an identified authoritative or contracted source |
| Calculated | Deterministically derived from identified inputs and rules |
| Estimated | Model-, comparable-, heuristic-, or assumption-based result |
| Unavailable | Not obtained, not evaluated, stale beyond policy, or insufficient evidence |

Frontend wording and API enums must remain consistent.

### 8.2 Material field metadata

Material fields should expose, as applicable:

- `status`;
- `source_refs`;
- `source_label`;
- `source_effective_at` or `as_of`;
- `last_synced_at`;
- `computed_at`;
- `method_version`;
- `confidence`;
- `limitations`;
- `user_overridden`;
- `default_origin`.

A contract change requires ADR review and backward-compatibility consideration.

### 8.3 Freshness panel

The dossier must show a compact source-age panel for:

- parcel geometry;
- assessment;
- zoning;
- recorded sales;
- L&I or code events;
- tax status;
- sheriff or forced-sale information;
- verdict computation.

### 8.4 Missing-data behavior

The system must not translate missing evidence into:

- no risk;
- no violation;
- buildable;
- clear title;
- no flood;
- zero taxes;
- zero cost;
- zero time;
- no restriction.

Unavailable evidence must remain unavailable.

### 8.5 Correction workflow

Every parcel dossier must provide **Report incorrect data**.

The correction record must capture:

- user ID;
- parcel number and market;
- field or section;
- verdict version;
- computed timestamp;
- source references and freshness state;
- user description;
- optional attachment or screenshot reference;
- triage status;
- resolution and resolution timestamp.

PII and attachments must follow security and retention rules.

---

## 9. Buildability requirements

### LR-B001 — Buildability checklist

The detailed buildability section must display checks such as:

- base zoning identified;
- base use permitted;
- minimum lot area;
- minimum lot width;
- maximum height;
- occupancy or floor-area limit;
- front, side, and rear yards;
- unit-density rule;
- overlay review;
- master-plan requirement;
- historic controls;
- street access;
- parking and loading;
- utilities;
- deed restrictions and easements;
- subdivision or consolidation;
- other market-specific requirements.

Each check must be `Pass`, `Fail`, `Potential issue`, `Not evaluated`, or `Not applicable`.

### LR-B002 — By-right wording

Do not present a basic base-district pass as unconditional construction approval.

Preferred wording:

> Appears dimensionally eligible under the listed base-district standards, subject to the limitations and checks below.

### LR-B003 — Historical variance context

Historical ZBA or appeal data may provide context, but the product must not promise approval probability without sufficient matched evidence.

Required behavior:

- identify sample size;
- distinguish dimensional and use relief;
- identify time window and geography;
- withhold percentages when evidence is too thin;
- label output **Historical approval context**;
- describe factors not captured by the dataset.

### LR-B004 — Buildability confidence

Confidence must consider:

- source completeness;
- district certainty;
- geometry quality;
- lot-shape complexity;
- overlay coverage;
- standard version;
- evaluated versus unevaluated checks.

A high confidence label cannot coexist with unresolved critical unknowns.

---

## 10. Opportunity and score requirements

### 10.1 Launch treatment

The existing Opportunity Score may remain for compatibility and sorting, but it must not be the sole headline recommendation.

### 10.2 Visible dimensions

Show separate dimensions:

- Buildability
- Economics
- Acquisition access or seller motivation
- Complexity and risk

### 10.3 Composite-score rules

No new customer-facing composite score may be introduced until:

- its inputs are defined;
- the rationale is documented;
- distribution is tested for useful ranking;
- gold-set behavior is reviewed;
- at least five paid-beta users assess its usefulness;
- the score does not hide missing data.

### 10.4 Naming

Prefer `Screening Score`, `Acquisition Fit`, or `LotScope Rank` over a conclusive `Opportunity Score` unless validated evidence supports the stronger name.

---

## 11. Underwriting requirements

### LR-U001 — Editable assumptions

The user must be able to inspect and edit:

#### Development program

- units;
- product type;
- gross building area;
- saleable or rentable area;
- floors;
- parking;
- basement;
- demolition requirement.

#### Acquisition

- purchase price;
- transfer taxes;
- title and closing;
- brokerage;
- legal;
- survey;
- environmental and other due diligence.

#### Construction

- hard cost per square foot;
- site work;
- demolition;
- utilities;
- excavation and foundation premium;
- landscaping;
- contingency.

#### Soft costs

- architecture;
- engineering;
- permits;
- entitlement;
- legal;
- insurance;
- developer overhead.

#### Financing and time

- equity contribution;
- interest rate;
- points and fees;
- construction duration;
- entitlement duration;
- sales or lease-up duration;
- taxes and carrying costs.

#### Exit

- finished value;
- selling commission;
- transfer taxes;
- concessions;
- closeout or warranty reserve.

### LR-U002 — Input provenance

Each assumption must identify:

- platform default;
- market default;
- parcel-derived;
- user-profile default;
- user override.

### LR-U003 — Scenarios

Every underwriting analysis must support:

- Base case
- Downside case
- Upside case

The scenarios must be deterministic, named, saved, and reproducible.

### LR-U004 — Sensitivity analysis

Support at least one useful two-dimensional sensitivity table:

- exit value versus construction cost; or
- purchase price versus exit value.

Additional sensitivity pairs may be added after customer evidence.

### LR-U005 — Underwriting profiles

Users can save reusable buy-box and underwriting profiles containing:

- target markets and areas;
- property types;
- unit range;
- maximum acquisition price;
- minimum margin or profit;
- construction-cost defaults;
- financing defaults;
- risk tolerance;
- variance tolerance;
- excluded ownership or condition classes.

Profiles must be versioned enough to reproduce prior analyses.

### LR-U006 — MAO transparency

Maximum allowable offer must show:

- formula;
- target return or margin;
- all major inputs;
- scenario;
- excluded costs;
- calculation timestamp.

Unknown required inputs must prevent a falsely precise MAO.

---

## 12. Information architecture requirements

### 12.1 Launch primary navigation

The preferred launch navigation is:

1. Home
2. Find Lots
3. Pipeline
4. Saved
5. Account

`Find Lots` may consolidate:

- Explore;
- Leads;
- Deal Feed;
- Sheriff or forced-sale opportunities;
- Assemblage opportunities;
- saved-search creation.

Existing stable routes may remain for compatibility, but the launch shell should not make every internal dataset an equal product destination.

An IA change requires review against ADR-0029 and may require a superseding ADR.

### 12.2 Parcel dossier information architecture

Recommended dossier sections:

1. Verdict
2. Buildability
3. Financials
4. Risks and records
5. Deal room

### 12.3 Deal room

The deal room contains:

- owner and permitted contact details;
- notes;
- pipeline stage;
- next action and due date;
- activities;
- offers and reports;
- documents;
- team assignment where supported.

### 12.4 Secondary features

Cash Buyers, Market Intelligence, Top Plays, and forced-sale-specific views may be filters, tabs, reports, or secondary menu items until usage proves they deserve primary navigation.

---

## 13. Onboarding requirements

### LR-O001 — Buy-box onboarding

Onboarding must collect concrete acquisition criteria rather than only explaining features.

Required steps:

1. property type;
2. Philadelphia geography;
3. price or economic constraints;
4. unit or project-size preference;
5. variance and risk tolerance.

### LR-O002 — Immediate results

After onboarding, show real matching opportunities. Do not send the user to an empty dashboard.

### LR-O003 — Guided activation

Guide the user to:

- open one parcel;
- inspect the likely program;
- change one financial assumption;
- save or add the parcel to pipeline;
- create an alert.

### LR-O004 — Progressive detail

Do not require every advanced assumption during registration. Use sensible defaults and let the user complete a full underwriting profile later.

---

## 14. Commercial packaging

Exact launch prices require owner approval and live customer testing.

### 14.1 Recommended launch experiment

| Plan | Positioning | Recommended range |
|---|---|---:|
| Free | Evaluate the product | $0 |
| Builder | Research and underwrite active opportunities | $149–$199/month |
| Acquisition Pro | Opportunity feeds, advanced workflow, contacts, larger exports | $299–$499/month |
| Team | Shared acquisition operation | Starting at $999/month |

### 14.2 Free-plan principles

Free should demonstrate the real Parcel Verdict but retain meaningful limits:

- limited complete verdicts;
- limited saved items;
- no advanced exports;
- no complete sensitivity analysis;
- no large-scale contact data;
- no high-frequency alerts.

### 14.3 Founding paid beta

Preferred experiments:

- first 25 users at $99/month locked while active; or
- $500 for a three-month assisted pilot; or
- $1,500–$3,000 for a team pilot with onboarding and weekly support.

Do not change Stripe products or public pricing without explicit owner approval.

### 14.4 Entitlement rules

Plan entitlements must be centralized, tested, and presented consistently in:

- pricing page;
- API authorization;
- frontend gating;
- checkout;
- billing portal;
- upgrade prompts.

---

## 15. Analytics and observability

### LR-A001 — Product analytics

Track at least:

- registration completed;
- onboarding completed;
- first search;
- first parcel opened;
- first complete verdict viewed;
- first assumption changed;
- first parcel saved;
- first saved search;
- first alert created;
- first pipeline deal;
- first report generated;
- owner reveal or credit use;
- pricing viewed;
- checkout started;
- subscription completed;
- subscription changed;
- subscription canceled.

Do not send owner PII, contact data, deed text, or sensitive search payloads to analytics.

### LR-A002 — Funnel definitions

Primary funnel:

> Visit → Register → Complete onboarding → View verdict → Save/add to pipeline → Return within seven days → Start checkout → Subscribe.

### LR-A003 — Error monitoring

Capture:

- frontend unhandled errors;
- API exceptions;
- failed background jobs;
- ingestion failure;
- stale datasets;
- billing-webhook failure;
- email failure;
- report generation failure;
- queue-health issues.

Errors must include correlation identifiers without leaking PII or secrets.

### LR-A004 — Launch dashboard

An internal launch dashboard or documented query set must report:

- activation rate;
- time to first verdict;
- first-session save rate;
- seven-day return rate;
- weekly active paid users;
- verdicts per paid user;
- saved searches per paid user;
- checkout conversion;
- cancellation;
- correction reports;
- data freshness;
- critical job failures.

---

## 16. Real-world validation

### LR-Q001 — Philadelphia gold set

Create at least 100 reviewed parcels covering:

- standard RSA rowhouse lots;
- undersized lots;
- oversized and double lots;
- corner and irregular lots;
- assemblage candidates;
- mixed-use districts;
- multifamily districts;
- industrial parcels;
- special-purpose districts;
- historic properties;
- flood exposure;
- public ownership;
- tax delinquency;
- access problems;
- developed properties appearing vacant;
- known permits;
- successful and unsuccessful zoning appeals.

### LR-Q002 — Review sources

Compare LotScope outputs against, as applicable:

- official zoning maps and code;
- issued permits;
- ZBA decisions;
- architect, zoning consultant, or expediter review;
- recorded sales;
- known development outcomes;
- authoritative parcel and tax records.

### LR-Q003 — Error severity

#### Critical

Could materially cause a user to pursue or buy based on a false premise:

- wrong district;
- wrong permitted use;
- wrong unit conclusion;
- missed master-plan requirement;
- false street-access conclusion;
- seriously misleading valuation;
- missing major known restriction presented as clear.

#### Material

Changes underwriting or diligence but is likely to be caught later:

- inaccurate buildable area;
- incorrect setback assumption;
- weak comparable selection;
- missing important risk flag;
- stale material record.

#### Minor

Presentation, labeling, or low-impact discrepancies.

### LR-Q004 — Gold-set launch gate

Philadelphia cannot be labeled commercially verified until:

- every parcel has a review status;
- no unresolved critical-error category remains;
- every known limitation is visible in product behavior or documentation;
- standard-parcel outcomes receive professional review;
- the owner accepts the remaining material-error profile.

Automated tests do not replace this review.

---

## 17. Commercial paid beta

### 17.1 Cohort

Recruit 10–15 paying design partners:

- five infill builders;
- three land investors;
- two acquisition managers;
- two land-focused brokers or agents;
- one or two zoning, architecture, or development consultants.

### 17.2 Required usage

Participants must evaluate real acquisition candidates, not only demonstration parcels.

### 17.3 Feedback record

For each reviewed deal, capture:

- parcel;
- customer goal;
- LotScope result;
- outside verification performed;
- trusted and untrusted fields;
- missing information;
- time saved;
- decision: pursue, pass, monitor, or offer;
- offer or pipeline action;
- correction report;
- willingness to continue paying.

### 17.4 Beta success evidence

Before broad public launch, require:

- at least five paying customers;
- at least five paying users returning weekly;
- at least three customers using LotScope on a genuine acquisition decision;
- at least one documented pursue/pass/offer decision materially supported by LotScope;
- no unresolved critical product-safety issue;
- a measured support and correction process.

---

## 18. Operational and commercial requirements

### LR-P001 — Billing

Verify in production-like conditions:

- checkout;
- subscription creation;
- upgrade;
- downgrade;
- cancellation;
- failed payment;
- webhook retries and replay;
- billing portal;
- entitlement update;
- credit grant and burn where applicable;
- refund procedure.

### LR-P002 — Email

Verify:

- account email;
- password reset;
- alert or digest email;
- billing email;
- support email;
- bounce and deliverability behavior.

### LR-P003 — Legal and policy surfaces

Publish owner-approved:

- Terms of Service;
- Privacy Policy;
- informational-analysis disclaimer;
- data-source and license disclosures;
- contact-data and outreach restrictions;
- refund policy;
- correction policy.

Claude Code may wire approved copy but must not invent final legal terms.

### LR-P004 — Support

Provide:

- visible support route;
- response ownership;
- parcel correction workflow;
- billing-support workflow;
- severity-based escalation;
- incident communication template.

### LR-P005 — Backups and recovery

Require:

- scheduled automated backups;
- off-machine retention;
- encryption;
- retention policy;
- monthly restore test;
- documented recovery-time objective;
- documented recovery-point objective;
- migration rollback and bad-verdict-recompute response.

### LR-P006 — CI and deployment protection

Require:

- protected `main`;
- required CI checks;
- no direct production commits;
- reviewed migration plan;
- production backup before risky migrations;
- post-deploy health and SHA verification;
- rollback plan.

### LR-P007 — Critical end-to-end tests

Automate:

1. register;
2. complete onboarding;
3. search;
4. open dossier;
5. inspect verdict;
6. edit an assumption;
7. save parcel;
8. add to pipeline;
9. create saved search;
10. start checkout;
11. upgrade;
12. generate report;
13. log out and back in;
14. complete the core mobile flow.

---

## 19. Performance and usability targets

These are launch targets, not guarantees:

- useful first result within five minutes of registration;
- parcel search interaction feels sub-second under normal load;
- cached dossier shell begins rendering quickly;
- complete verdict target remains approximately two seconds when precomputed;
- no unbounded frontend loading state;
- no silent partial failure;
- mobile supports the entire primary acquisition journey;
- accessibility checks cover keyboard navigation, labels, focus, and contrast on critical flows.

Measure before optimizing.

---

## 20. Success metrics

### 20.1 Activation

- median time to first complete verdict;
- percentage viewing a complete verdict in the first session;
- percentage saving or adding a parcel to pipeline in the first session.

### 20.2 Engagement

- weekly active paid users;
- parcels evaluated per active user;
- saved searches created;
- assumptions edited;
- pipeline actions completed;
- alerts acted upon.

### 20.3 Trust

- correction reports per 100 verdict views;
- critical and material error counts;
- percentage of material fields with current provenance;
- stale-dataset incidents;
- percentage of users who report trusting the screening result.

### 20.4 Commercial

- paid pilots;
- checkout conversion;
- monthly recurring revenue;
- paid retention;
- cancellation reasons;
- support burden per paid account.

### 20.5 Initial target hypotheses

Use as hypotheses to test, not unquestioned benchmarks:

- median time to first verdict under five minutes;
- at least 30% of new users save or pipeline a parcel in the first session;
- at least 20% create a saved search within seven days;
- paying users evaluate at least five parcels per week;
- at least 60% of paid-beta users return weekly;
- at least 70% of paid-beta users remain after two months.

---

## 21. Phased delivery

### Phase LR-0 — Recon and launch baseline

- map current implementation to this amendment;
- identify already-complete requirements;
- identify documentation drift;
- identify contracts and ADRs affected;
- establish baseline metrics;
- produce a P0/P1/P2 backlog.

**Exit:** owner approves the gap matrix and slice sequence.

### Phase LR-1 — Truth and trust foundation

- field-state taxonomy;
- provenance and freshness presentation;
- missing-data behavior;
- correction workflow;
- documentation alignment;
- gold-set structure and review process.

**Exit:** trust contract is tested and the gold-set program is operational.

### Phase LR-2 — Decision-first Parcel Verdict

- screening recommendation;
- likely program;
- financial headline;
- deal killers;
- required next checks;
- visible score components.

**Exit:** an experienced user can understand pursue/investigate/pass reasoning in approximately 30 seconds.

### Phase LR-3 — Professional underwriting

- editable assumptions;
- input origins;
- scenarios;
- sensitivity;
- profiles;
- transparent MAO.

**Exit:** users can reproduce their own underwriting and explain the result.

### Phase LR-4 — Focused acquisition experience

- launch navigation;
- dossier sections;
- buy-box onboarding;
- immediate matched opportunities;
- guided activation;
- secondary-feature de-emphasis.

**Exit:** first-session activation is possible without founder explanation.

### Phase LR-5 — Commercial and observability hardening

- analytics;
- error monitoring;
- billing;
- email;
- support;
- owner-approved legal copy;
- pricing experiment configuration.

**Exit:** paid usage can be measured and supported safely.

### Phase LR-6 — Operational hardening

- branch protection;
- backup and restore;
- critical E2E;
- alerting;
- incident runbook;
- performance and accessibility checks.

**Exit:** a production defect can be detected, contained, and recovered.

### Phase LR-7 — Controlled paid beta

- recruit cohort;
- onboard;
- evaluate real deals;
- track trust, usage, corrections, and retention;
- fix only launch-critical issues.

**Exit:** beta-success evidence is met or the product is revised.

### Phase LR-8 — Launch gate review

- produce evidence against every gate;
- record exceptions and owner acceptance;
- decide: public launch, extend beta, or pause.

---

## 22. Priority rules

### P0 — Blocks paid beta or creates material trust risk

- wrong or misleading decision output;
- missing-data presented as clear;
- unverifiable financial black box;
- broken billing or authentication;
- no correction route;
- no production error visibility;
- no backup/restore plan;
- critical journey failure;
- legal or PII exposure.

### P1 — Required before broad public launch

- decision-first hero;
- complete underwriting scenarios;
- focused navigation;
- buy-box onboarding;
- gold-set completion;
- product analytics;
- source-age visibility;
- support process;
- critical E2E.

### P2 — Improve after launch evidence

- advanced score model;
- additional sensitivity dimensions;
- richer team collaboration;
- deeper buyer intelligence;
- expanded reports;
- additional acquisition automations.

### P3 — Deferred

Everything in §5.2 unless specifically promoted by measured customer evidence.

---

## 23. Definition of done for this amendment

The amendment is fulfilled only when:

- Philadelphia is the clear commercial flagship;
- the primary customer and promise are reflected in product and pricing;
- the primary journey works on desktop and mobile;
- material fields expose trust and freshness;
- buildability limitations are explicit;
- underwriting is editable and scenario-based;
- the 100-parcel gold set has been reviewed;
- billing, email, analytics, monitoring, support, and recovery are operational;
- real paying customers use the product for real acquisition decisions;
- the public-launch gate review is documented and approved.

---

## 24. Anti-patterns during launch readiness

Never:

- add a market to create an impression of progress;
- hide uncertainty behind a score;
- treat a base-district check as final approval;
- use missing values as zero;
- redesign unrelated surfaces while changing the verdict;
- modify pricing and entitlements in the same unreviewed change;
- introduce a new analytics or monitoring vendor without privacy review;
- ship legal copy written as if it were approved counsel;
- build all phases in one branch;
- merge a migration without backup and rollback instructions;
- delete stable secondary features merely because they are de-emphasized;
- substitute automated tests for real parcel validation;
- call free registrations proof of product-market fit.
