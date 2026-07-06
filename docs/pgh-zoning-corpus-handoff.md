# Pittsburgh Zoning Code — corpus acquisition (HANDOFF, corpus-gate STOP)

**Slice 5 stopped at the corpus gate (2026-07-06).** Per the absolute corpus gate, `zoning_standard` rows and any buildability logic must come from **verbatim official code text** — never summaries, practitioner guides, or memory. Automated acquisition from the build environment is **not possible**:

- **eCode360 mirror** (`ecode360.com/PI6865`): HTTP **403** (Cloudflare anti-bot — same as Harrisburg's eCode360).
- **Municode** (`library.municode.com/pa/pittsburgh`): a JavaScript app; the shell returns 200 but the code text is **403 via WebFetch** and not served as plain text.

So this is the Harrisburg pattern again: **you export the text via a normal browser (compliant), and I author from it.**

## What to acquire (Title Nine — the Pittsburgh Zoning Code)
Primary source: **Municode** `library.municode.com/pa/pittsburgh/codes/code_of_ordinances` → `PIZOCO_TITNINEZOCO`. Export (print-to-PDF or copy) the **district regulations** and, critically, **every dimensional/use table** — the eCode360 lesson is that these often live as **separate attachments/exhibits**, and the corpus is incomplete without them. Specifically:

1. **Article IV — Zoning Districts** (the per-district regulations): residential (Ch 903), commercial/office (Ch 904), etc. — each district's **use table** and **dimensional standards** (min lot area/width, setbacks, height, lot coverage, density/units-per-acre).
2. **Any exhibit/attachment tables** referenced from those chapters (use matrices, dimensional matrices) — inventory them explicitly; a chapter that says "see Table 903.03.A" needs that table exported too.
3. Definitions (Ch 926) for terms the standards depend on, if the standards cite them.

Place the exports in **`backend/corpus/pgh/`** (gitignored, like `backend/corpus/hbg/`). Tell me the filenames + which districts/tables each covers.

## District taxonomy (from the WPRDC zoning GIS — labels only, NOT standards)
40 districts, e.g.: **R1D-{VL,L,M,H,VH}** (single-unit detached by density), **R1A-{M,H,VH}** (single-unit attached), **R2-{L,M,H,VH}** (two-unit), **R3-{L,M}** (three-unit), **RM-{M,H}** (multi-unit), **LNC/NDO/HC** (neighborhood commercial/office/highway), **GI/NDI/EMI** (industrial/institutional), **GT-{A..E}** (Golden Triangle downtown), **RIV-*** (riverfront), **P** (parks), **H** (hillside), **AP/CP** (planned unit dev). These codes + names come from the GIS and are safe to use as the district *list*; the regulatory *standards* for each still require the corpus text above.

## What proceeds without the corpus (when Slice 5 resumes)
- **Zoning-districts GIS loader** → `zoning_district` (market='pgh'), spatial-first resolution. Note: the GIS `geometry` is WKT in a non-2272 projection (UTM-like easting/northing ~592k/4468k) — confirm the SRID and `ST_Transform` to 2272 at load. This gives parcels their resolved district code + name (honest; buildability stays "standards not loaded" until the corpus).
- **`zoning_standard` authoring** (`code_version='pgh-provisional-2026'`): only after the corpus lands — well-established figures only, NULL every unconfirmed field, density only where the corpus states it, cited in reasons.
- **25-parcel spot-verification packet** against the city's official zoning map; provisional cap stays until a local expert (zoning attorney/expediter) review — no Pittsburgh reviewer relationship yet.

**Blocking:** `zoning_standard` rows + buildability for pgh. **Not blocking:** everything else in the pilot (parcels, comps, distress, violations, inventories all live).
