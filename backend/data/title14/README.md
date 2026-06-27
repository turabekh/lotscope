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
- `sections.jsonl` — the real corpus you provide (the default path the loader
  reads). Populate it with the actual Title 14 section text, then run
  `make ingest-title14`. Override the path with `make ingest-title14 FILE=...`.

Requires `VOYAGE_API_KEY` in `backend/.env`.
