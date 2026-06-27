# Title 14 RAG corpus

The "Ask the Parcel" feature grounds answers in this corpus. The loader
(`lotscope.ai.corpus`, run via `make ingest-title14`) reads a **JSONL** file —
one record per line — chunks each record, embeds the chunks with Voyage, and
upserts them into the `document` table under `source = "title14"` (a re-run
replaces the source entirely, so it is idempotent).

## Record format

```json
{ "section": "14-701 (RSA-5)", "title": "RSA-5 ...", "text": "full section text ..." }
```

- `section` — the citation identifier the model will cite (required).
- `title` — a human label (optional).
- `text` — the section text to embed and retrieve (required).

## Files

- `sections.sample.jsonl` — a tiny **provisional** sample so the pipeline is
  demonstrable. Its content is summarized and **must not** be treated as the
  authoritative code.
- `sections.jsonl` — the corpus the loader reads by default. It covers every
  base district — residential (RSD, RSA-1..6, RTA, RM-1..4), mixed-use (RMX),
  commercial (CA, CMX-1..5), industrial (IRMX, ICMX, I-1/2/3/P), and special
  purpose (SP-INS, SP-CIV, SP-PO-A/P, SP-ENT, SP-STA, SP-AIR) — transcribed from
  the **Philadelphia Zoning Code Base Districts Quick Guide (Dept. of Planning &
  Development, February 2026)** — Tables 14-701-1/-2/-3/-4 (dimensional
  standards) and 14-602-1/-2/-3/-4 (use tables). Override the path with
  `make ingest-title14 FILE=...`.

## Source

Authoritative tables: Philadelphia Zoning Code Base Districts Quick Guide,
February 2026 (`phila.gov`). The full Title 14 text lives at American Legal
Publishing (`codelibrary.amlegal.com/codes/philadelphia`) but is bot-protected.
The same source backs the `zoning_standard` table seeded by `lotscope.zoning.seed`.
Every base district is transcribed, covering 100% of zoned parcels. The
special-purpose (SP-*) districts are master-plan driven: their seeded standards
record permitted uses and any stated dimensional limits, but real development
requires an approved master plan — a nuance the corpus text spells out for
grounded answers.

Requires `VOYAGE_API_KEY` (set in the repo-root `.env`).
