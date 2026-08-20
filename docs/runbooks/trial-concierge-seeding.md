# Runbook — concierge seeding for a trial account

Fifteen minutes, start to finish, from the moment the trial user registers. Everything here uses surfaces that already exist; nothing in this runbook requires a deploy.

Written for the first external trial user (a sheriff-sale-only buyer, six vacant lots). The parcel ids in §2–§5 are hers; the shape is reusable.

**Read `docs/preflight/trial-user-preflight-2026-08-20.md` before running this.** Two of its findings change what you seed.

---

## 0. Before she registers (do this now, once)

- [ ] Confirm you can reach admin as an admin account.
- [ ] Have the six parcel ids to hand (§2).
- [ ] Read §6 — *what not to do*. One item there is a decision, not a step.

---

## 1. Find the account and lift the tier (2 min)

1. `GET /admin/users` — find her by email. Note the numeric `user_id`.
2. `PATCH /admin/users/{user_id}` with `{"tier": "investor"}`.
   Valid tiers: `free`, `pro`, `investor`, `enterprise`. **Investor**, not pro — pro leaves `buyer_intel` gated and she will hit an upgrade prompt on the verdict tab of her own lot.
3. Verify by re-reading `GET /admin/users` and confirming `tier` reads `investor`. Do not verify from the PATCH response alone.

---

## 2. Seed the saved list (3 min)

Title it **"Your lots — graded"**. Neutral, possessive, no verb that implies we went looking.

`POST /watchlist` once per parcel:

| parcel | address |
|---|---|
| `phl:201133900` | 1943 N MARSHALL ST |
| `phl:191357500` | 2138 N FAIRHILL ST |
| `phl:062284300` | 810 N 42ND ST |
| `phl:243169100` | 3966 PENNSGROVE ST |
| `phl:243037700` | 3862 ASPEN ST |
| `phl:362363700` | 1329 GROVE ST |

Then `GET /watchlist` and count six. A 201 per call is not the check; the list read is.

**Two of these carry a known wrong flag** — `phl:362363700` and `phl:243037700` show a medium-severity delinquency naming a party who is a grantor on her own deed (pre-flight §1.4). Seed them anyway; they are her lots and omitting them would be the more visible choice. Have the explanation ready (§5).

---

## 3. Pre-load the pipeline (2 min)

`POST /pipeline` for the same six parcel numbers, so the pipeline board is not empty on first open. Verify with `GET /pipeline` — six items.

Leave every one in the default entry stage. Do not assign stages, offers, or next actions: a pipeline that already has opinions about her deals reads as presumptuous, and she has not told us her process.

---

## 4. Create the two saved searches (4 min)

`POST /saved-searches`, one per cluster. Centroids computed from her own parcels' geometry.

**"Vacant lots near your Mantua triangle"**

```json
{
  "market": "phl",
  "center": { "lat": 39.96846, "lng": -75.20362 },
  "radius_m": 500,
  "vacant_only": true,
  "min_opportunity_score": 30,
  "limit": 200
}
```

**"Vacant lots near your Norris corridor"**

```json
{
  "market": "phl",
  "center": { "lat": 39.98248, "lng": -75.14436 },
  "radius_m": 500,
  "vacant_only": true,
  "min_opportunity_score": 30,
  "limit": 200
}
```

Then `POST /saved-searches/{search_id}/run` on each and confirm a non-zero count. **A saved search that returns nothing is worse than no saved search** — if either comes back empty, drop `min_opportunity_score` before you widen the radius, because the score threshold is the cheaper lever and the radius is the one that changes what the search means.

**Do not set `sheriff_sale_only`.** It filters on the Revenue delinquency flag, which has zero overlap with the live sheriff-sale calendar (pre-flight §3). It would silently return nothing useful and she sources exclusively at sheriff sales — this is the one filter she would most expect to work.

---

## 5. Talking points from the assessment sweep (2 min to prepare)

Import exactly one number. From pre-flight §2:

> **1329 GROVE ST** (`phl:362363700`) — assessed $83,900, modelled market $58,126, over-assessed, **estimated ~$361/yr** if appealed. **Medium confidence.**

Say it with the caveat attached, in one breath: *a thin comparable set, an order-of-magnitude indication, not a number to file on.*

**Do not import the other six.** $1,681 on 59 E GARFIELD, $1,117 on 128 E WELLENS, and the four like them are developed properties measured against vacant-land comps — a category error, not a saving (pre-flight §2). Found money claimed and wrong is worse than none, and she is the one person who will know instantly that her rowhouse is not worth $53,195.

If she asks about her developed parcels: say plainly that LotScope models vacant and infill land, that the assessment read on a built property compares it to land sales, and that we do not stand behind those numbers yet.

**The two flags to get ahead of.** On `phl:362363700` and `phl:243037700` she will see a medium-severity delinquency naming MCNAIR KENNETH and ASBELL WILLIAM respectively. Both are grantors on her own sheriff's deeds. The join fails to split multi-party grantor lists on `;`; it affects 297 Philadelphia parcels, 201 of them vacant; the debt is correctly kept out of the distress score in both cases. Tell her before she finds it.

**The thing worth showing off.** `phl:191357500`'s deed is keyless upstream — RTT carries it with a null OPA account number, so the city's own transfer record cannot say which parcel it belongs to. We have it on the right parcel with the right grantor, price and date. That is one of her lots, and it is the clearest demonstration in the account that this is more than a data mirror.

---

## 6. Verification pass, as her account (2 min)

Log in as her — or as a throwaway account at the same tier — and walk the path she will walk. Assert what renders, not what the API returns.

- [ ] All six lots render in the saved list, each with an address and a score.
- [ ] Open `phl:201133900`: snapshot paragraph mentions the complied violation as history and the prior owner's discharged delinquency. **If it says "active" anywhere, stop** — the fix is not deployed.
- [ ] Open `phl:191357500`: snapshot says two violations are still open. Both directions must be right, not just the quiet one.
- [ ] Verdict tab shows no upgrade prompt on `buyer_intel` — if it does, the tier flip did not take.
- [ ] Pipeline board shows six items.
- [ ] Both saved searches return results.
- [ ] No admin-only surface is reachable: no `/admin` link in the sidebar, no ops or dataset-health chip, no job controls.
- [ ] Deal tab: note which paid CTAs appear before you send. See §7.

---

## 7. What NOT to do

**Do not leave a paid CTA as a paywall in her first-session path.** The **$79 appeal packet** renders on the deal tab of any parcel the assessment surface calls over-assessed — including her developed parcels, where the arithmetic is a category error (§5). Two acceptable resolutions, one decision required before the send: keep her first session on the six vacant lots, where only 1329 GROVE ST triggers it; **or** comp the packet for her account so the number is never behind a price. Do not do neither.

**Do not open the neighbour's page in front of her without framing it.** `1941 N MARSHALL ST` (`phl:881000216`) shows "strong assemblage potential" with **her lot as one of two candidates**. That page is the neighbour's acquisition thesis about her land. Her own page correctly says there is no assemblage play for her, because only 1941 touches both vacant lots. If the assemblage story is worth telling, tell it as *what your lot is worth to the building next door* — never as a screen that helps someone buy from her. Two caveats belong with it: the panel does not model the existing >4-unit building on 1941, and the other candidate (`1935 N MARSHALL ST`) is **owned by the City of Philadelphia** while the panel shows it as an ordinary vacant lot. See `docs/preflight/send-gate-verification-2026-08-20.md` §5.

**Do not open `3862 ASPEN ST` without warning her first.** OPA has not processed her 2025 deed, so the page names **WM ASBELL** as owner, and the owner-portfolio panel reads "1 parcel, $48,900" under his name. Her deed history is correct and shows the purchase. Say it before she reads it.

**Do not seed anything that implies surveillance.** Everything in this runbook is her own public purchase history — deeds she signed, recorded at the Department of Records, and the city's own assessment of lots she owns. Frame it that way every time: *these are your lots, graded against public records.* Never present skip-trace output, mailing-address inference, or portfolio aggregation as something we assembled about her. The absentee signal in particular is a scoring input derived from a public mailing address; it is never a talking point.

**Do not pre-fill her process.** No stages, no offers, no next actions, no notes. A seeded list is hospitality; a seeded opinion is presumption.

**Do not send while a sweep or deploy is running.** `compose up -d` recreates the worker; a mid-flight recompute can leave her opening a parcel whose verdict is being rewritten under her.

**Do not claim a number the pre-flight flagged.** If it is not in §5, it does not go in the email.
