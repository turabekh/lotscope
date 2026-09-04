# Data licences

## Philadelphia — OpenDataPhilly / city open data

Every city dataset we ingest (OPA assessments, PWD parcels, RTT transfers, tax
delinquency, L&I violations and permits, vacancy indicators, zoning base
districts and overlays, RCOs, street centerlines, historic districts, ZBA
appeals) is published as-is through OpenDataPhilly and the Carto SQL API, with
no warranty of accuracy or fitness. Product output must carry that posture: the
city's terms are hold-harmless, so derived facts are shown with their source and
as-of timestamp rather than asserted as ground truth.

## L&I — violations, permits, demolitions, unsafe/imminently-dangerous cases

Published by Licenses & Inspections through OpenDataPhilly and the Carto SQL API under the
city's open-data terms: free to use and redistribute, no warranty, no fitness guarantee. Case
status changes after the nightly pull, so an open violation is a signal to verify live before
it is relied on, not a finding. Never present a closed case as open, or the absence of a case
as a clean record — L&I records what was reported, not what exists.

## RTT — recorded real-estate transfers

The Department of Records' `rtt_summary`, published through the same Carto SQL API and the
same city open-data terms. It is a public record of recorded documents, so grantor and
grantee names are lawfully republishable, but the deed image itself is not in the dataset and
consideration can be nominal ($1 transfers, sheriff's deeds, intra-family conveyances). Comps
drawn from it exclude those document types for that reason. Recording lags the sale by weeks,
so a missing recent transfer means "not yet recorded", never "not sold".

## FEMA — national flood hazard layer

Public domain. Flood-zone reads are a screening signal, not a determination; a
FIRMette or an elevation certificate is the authoritative artefact.

## Sheriff sales — CivilView

Scraped from the public listing site. Postponements and withdrawals happen
between scrapes, so a listing is a scheduled-auction signal and is verified live
before it is relied on.

## Third parties

BatchData (skip trace) carries its own terms including a 30-day cache limit; see
`docs/PLAN.md` Step 5.2 before enabling it. Regrid is not currently ingested.
