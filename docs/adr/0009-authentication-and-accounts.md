# 9. Authentication and accounts

Date: 2026-06-27

## Status

Accepted

## Context

Build-order step 11 (accounts & billing) needs user accounts and authentication. The auth model is an ADR-level decision (§4). The platform is an in-house modular monolith with no external service dependencies named in `CLAUDE.md`, so the question is build-vs-buy and the token model.

## Decision

**In-house, stateless JWT bearer auth — no external identity provider.** Consistent with the rest of the stack and avoids a new runtime service.

- **Passwords** are hashed with **argon2** via `pwdlib` (recommended preset). Plain passwords are never stored or logged.
- **Access tokens** are JWTs (HS256, signed with `SECRET_KEY`) with claims `sub` (user id), `role`, and `exp`. Token creation/verification lives in `accounts.security`; all model access is centralized in the `accounts` module.
- **`User`** (`app_user` — `user` is a reserved word) holds `email` (unique), `hashed_password`, `full_name`, `role`, `tier`, and `is_active`. **`role`** (`user`/`admin`) governs permissions; **`tier`** (`free`/`pro`/`team`) is the billing plan that Stripe will set later.
- **Endpoints:** `POST /auth/register`, `POST /auth/login` (returns a bearer token), `GET /auth/me`. `get_current_user` and `require_admin` are FastAPI dependencies built on `HTTPBearer`; auth failures map to 401, permission failures to 403 via the shared `ErrorResponse`.
- **Email** is validated by pattern and normalized to lowercase (no `email-validator` dependency yet).

The `accounts` service interface keeps the door open for SSO/OAuth, refresh tokens, and Stripe without changing callers.

## Consequences

- Stateless tokens mean no server-side session store; logout is client-side token discard. Revocation before expiry needs a denylist — a follow-up; mitigated by keeping access tokens short-lived (`access_token_expire_minutes`, default 60).
- **`SECRET_KEY` must be ≥32 bytes in production** (RFC 7518 for HS256); the default value is a placeholder for local only.
- **Deferred** (not in this slice): refresh tokens, SSO/OAuth, password reset and email verification, Stripe billing, usage metering, team seats, and auth rate limiting. **Existing endpoints are not yet auth-gated** — wiring tier limits and protecting the verdict/ask/comps routes is the next accounts slice.
