# Data licences

## Philadelphia — OpenDataPhilly / city open data

Every city dataset we ingest (OPA assessments, PWD parcels, RTT transfers, tax
delinquency, L&I violations and permits, vacancy indicators, zoning base
districts and overlays, RCOs, street centerlines, historic districts, ZBA
appeals) is published as-is through OpenDataPhilly and the Carto SQL API, with
no warranty of accuracy or fitness. Product output must carry that posture: the
city's terms are hold-harmless, so derived facts are shown with their source and
as-of timestamp rather than asserted as ground truth.

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
