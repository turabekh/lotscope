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
| `SMTP_USER` | username | *(empty)* | `postmaster@<domain>` |
| `SMTP_PASSWORD` | password / API key (**secret**) | *(empty)* | `<key>` |
| `SMTP_USE_TLS` | STARTTLS | `false` | `true` |
| `EMAIL_FROM` | From address | `alerts@lotscope.app` | `alerts@lotscope.app` |
| `EMAIL_FROM_NAME` | From display name | `LotScope PHL` | `LotScope PHL` |

## What turns on when email is enabled

Enabling SMTP activates **all** email paths on their crons (`worker.py`), not just one:

- **User-facing:** watchlist digests (daily 13:00 / weekly Mon 13:30), feed digests (13:15), saved-search
  match alerts (09:00), deal reminders (13:45).
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

## Production — enabling real delivery

Prod does **not** use Mailpit (a catcher can't deliver to real inboxes). Steps:

1. **Pick a provider** (Mailgun, AWS SES, Postmark, SendGrid — all standard SMTP).
2. **Verify the sending domain** for `alerts@lotscope.app` in that provider: add the SPF + DKIM DNS records
   for `lotscope.app` (or a subdomain). Without this, mail bounces or lands in spam. This is a prerequisite,
   not optional.
3. **Set the env vars** in `/home/turaboy/lotscope/.env` on the VM (the file docker-compose reads). Keep
   `SMTP_PASSWORD` out of any shared channel.
4. **Restart the app** so it re-reads config:
   ```
   docker compose --profile app up -d api worker
   ```
5. **Verify** the sender is live, then send one test to an admin before the crons fan out:
   ```
   docker compose exec -T api python -c "
   from lotscope.core.config import get_settings
   print('email enabled:', get_settings().smtp_host is not None and get_settings().smtp_host != '')"
   ```
6. Watch the first scheduled runs; the ops digest is quiet-when-green, so absence of an ops email is normal
   when the fleet is healthy.

To roll back: blank `SMTP_HOST` in the VM `.env` and restart `api`/`worker` — all email goes quiet again.
