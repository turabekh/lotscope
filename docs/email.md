# Email setup

LotScope sends transactional/notification email through **plain SMTP** (`notifications/email.py`
`SmtpEmailSender`, stdlib `smtplib`). It is provider-agnostic: the app never talks to a vendor API, so
switching providers is purely an env change — no code.

`smtp_host` is the **single on/off switch**. If `SMTP_HOST` is blank, `get_email_sender` returns `None`
and **every** email path becomes a quiet no-op.

## Config keys

| Env var | Meaning | Local (Mailpit) | Production example (Mailgun) |
|---|---|---|---|
| `SMTP_HOST` | SMTP server; blank = email off | `localhost` | `smtp.mailgun.org` |
| `SMTP_PORT` | port | `1025` | `587` |
| `SMTP_USER` | username | *(empty)* | `postmaster@mg.parcelphl.online` |
| `SMTP_PASSWORD` | password / API key (**secret**) | *(empty)* | `<key>` |
| `SMTP_USE_TLS` | STARTTLS | `false` | `true` |
| `EMAIL_FROM` | From address | `alerts@parcelphl.online` | `alerts@parcelphl.online` |
| `EMAIL_FROM_NAME` | From display name | `LotScope PHL` | `LotScope PHL` |
| `EMAIL_REPLY_TO` | optional Reply-To (blank = replies to `EMAIL_FROM`) | *(empty)* | `support@parcelphl.online` |
| `EMAIL_ALLOWLIST` | staged-rollout recipient gate (see below) | `[]` | `[]` once fully live |

**Sending domain is `parcelphl.online`** (the domain users actually visit — best deliverability alignment and brand recognition). It is a pure env value: to move it, change `EMAIL_FROM` (and re-verify DNS for the new domain). Nothing in code hardcodes it.

## Staged rollout — `EMAIL_ALLOWLIST`

Enabling `SMTP_HOST` turns on **every** email path at once (see below). That is not an acceptable first
flip. `EMAIL_ALLOWLIST` is the smallest honest control: a list of recipient addresses that, **when
non-empty**, suppresses mail to anyone not on it (logged as `email_suppressed_by_allowlist`, no send).
Empty = send to everyone. Recommended order:

1. **Ops digest / your inbox only** — set `EMAIL_ALLOWLIST=["you@parcelphl.online"]`. Only your own address
   receives; every user path is gated. Watch deliverability (SPF/DKIM pass, not spam-foldered).
2. **Widen** — add a few trusted addresses; confirm List-Unsubscribe + rendering across clients.
3. **Go live** — set `EMAIL_ALLOWLIST=[]` and restart. All users now receive on the normal crons.

**One-variable rollback at any stage:** blank `SMTP_HOST` (all email → quiet no-op), or narrow
`EMAIL_ALLOWLIST` back to your address. Restart `api`+`worker` after either.

User-facing mail carries a `List-Unsubscribe` header (RFC 8058 one-click) pointing at the per-user
unsubscribe token URL; ops/admin mail does not.

## What turns on when email is enabled

Enabling SMTP activates **all** email paths on their crons (`worker.py`), not just one:

- **User-facing:** watchlist digests (daily 13:00 / weekly Mon 13:30), feed digests (13:15), saved-search
  match alerts (09:00), deal reminders (13:45), the "sales this week" calendar digest (Mon 08:00,
  quiet-when-empty, Pro+ only).
- **Admin-facing (ops):** ops health digest (10:00, quiet-when-green), failure alerts (05:30, post-ingest).

So turning SMTP on in production means real users start receiving mail at the next scheduled run. Test
locally with Mailpit first.

## Local development — Mailpit

`make up` starts a **Mailpit** mail-catcher (`docker-compose.yml`, `dev` profile) alongside db/redis/martin.
It accepts any SMTP on `localhost:1025` and captures everything — nothing leaves your machine.

1. Copy `.env.example` → `.env` (its SMTP block already points at Mailpit).
2. `make up` (starts Mailpit; it never runs in production — the `dev` profile is not activated by the
   deploy's `--profile app`).
3. Trigger an email — e.g. run a worker job, or a one-off send:
   ```
   cd backend && uv run python -c "
   import asyncio
   from lotscope.core.config import get_settings
   from lotscope.notifications.email import get_email_sender
   async def main():
       s = get_email_sender(get_settings())
       await s.send(to='you@example.com', subject='Mailpit test', html='<b>hi</b>', text='hi')
   asyncio.run(main())"
   ```
4. Open **http://localhost:8025** to view the captured message.

(If you run the backend inside the docker `app` profile instead of on the host, set `SMTP_HOST=mailpit`.)

## Production — enabling real delivery (Mailgun on `parcelphl.online`)

Prod does **not** use Mailpit (a catcher can't deliver to real inboxes). The app change is done — this is
now provider config + DNS. Provider is **Mailgun** (any standard-SMTP provider works; the steps are the same
shape).

### Step 1 — Mailgun console (owner)
1. **Add a sending domain**: Mailgun → Sending → Domains → **Add New Domain**. Use a subdomain —
   **`mg.parcelphl.online`** (Mailgun's recommendation; keeps the root domain's own mail reputation
   separate). Region: US (or EU — match `SMTP_HOST` accordingly).
2. Mailgun shows the DNS records to add (Step 2). Add them at the `parcelphl.online` registrar, then click
   **Verify** in Mailgun until all rows go green (DNS can take up to a few hours).
3. **Fetch SMTP credentials**: Domain → **SMTP** tab → `postmaster@mg.parcelphl.online` + a generated
   password. That password is `SMTP_PASSWORD` (secret — never in chat/VCS).

### Step 2 — DNS records to paste at the `parcelphl.online` registrar
Exact values come from the Mailgun domain page; the set is standard. `@`/host names are relative to
`parcelphl.online`:

| Type | Host / Name | Value | Purpose |
|---|---|---|---|
| `TXT` | `mg` | `v=spf1 include:mailgun.org ~all` | **SPF** — authorizes Mailgun to send |
| `TXT` | `<selector>._domainkey.mg` | `k=rsa; p=<long key from Mailgun>` | **DKIM** — signs mail (selector shown by Mailgun, e.g. `mx`/`k1`) |
| `MX` | `mg` | `10 mxa.mailgun.org` and `10 mxb.mailgun.org` | receiving/bounce handling |
| `CNAME` | `email.mg` | `mailgun.org` | click/open tracking (optional but recommended) |
| `TXT` | `_dmarc` | `v=DMARC1; p=none; rua=mailto:dmarc@parcelphl.online` | **DMARC** — start at `p=none` (monitor), tighten to `quarantine`/`reject` after mail is clean |

DKIM + SPF are prerequisites — without them mail bounces or spam-folders. DMARC at `p=none` is safe to add
immediately and gives visibility before enforcing.

### Step 3 — set env on the VM (owner appends the secret)
In `/home/turaboy/lotscope/.env` (the file docker-compose reads) set the non-secret keys:
```
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@mg.parcelphl.online
SMTP_USE_TLS=true
EMAIL_FROM=alerts@parcelphl.online
EMAIL_ALLOWLIST=["<your-inbox>@parcelphl.online"]   # stage 1: your inbox only
```
then append `SMTP_PASSWORD=<key>` off-channel. Restart: `docker compose --profile app up -d api worker`.

### Step 4 — verify + walk the staged rollout
```
docker compose exec -T api python -c "
from lotscope.core.config import get_settings
s = get_settings()
print('email enabled:', bool(s.smtp_host), '| allowlist:', s.email_allowlist)"
```
Confirm the Mailgun domain reads **verified**, send/trigger one message to your allowlisted inbox, and check
it lands (not spam) with SPF/DKIM = pass. Then widen and finally clear `EMAIL_ALLOWLIST` per the staged order
above, checking Mailgun's **bounces/complaints** views after the first real digest run.

**Rollback (any stage):** blank `SMTP_HOST` in the VM `.env` (all email → quiet no-op) or narrow
`EMAIL_ALLOWLIST` back to your inbox; restart `api`/`worker`.
