# LotScope
An AI acquisitions analyst that works Philadelphia land for you.

Who: people who buy vacant lots in Philadelphia — sheriff-sale buyers first, infill developers second.
What they pay for: (1) a Sale Packet — every vacant lot on a sheriff-sale date screened against their buy box, with MAO, red flags and comps; (2) Lot Diligence — a pre-closing checklist on one parcel; (3) later, a monthly Analyst plan with a nightly brief.
The product is the Analyst conversation. The Lot page is evidence the Analyst opens. Deals is the pipeline. There are no other screens.
Market: Philadelphia only.
One metric: paid packets this week.

Rules:
- Every derived fact carries source, source_url and computed_at/fetched_at. A fact the Analyst cannot source is labelled "unverified", never asserted.
- Anything a buyer will check (owner, last deed, open violations, sale status) is verified live against the primary source at answer time; the nightly ingest is an index, not the truth.
- Ship behind a flag, measure on real users. No feature gate, no ADR, no version ceremony.
- Tests cover money math: zoning eligibility, deal/MAO, delinquency attribution, party matching, comp selection, parcel-key reconciliation. Everything else is tested by using it.
- Provenance on every derived field. That is the whole rulebook.
