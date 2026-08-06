# Going public

Letting **anyone** connect their own Search Console and Analytics, rather than a
fixed list of test users.

`deploy/README.md` covers *how to run this on a server*. This file covers the
extra things that only matter once strangers can sign up, in the order they have
to happen. Read `deploy/README.md` first — it is the substrate, this is the
delta.

---

## The one thing that blocks everything else

The current redirect URI is `http://localhost:8000/v1/google/callback`. That
address resolves **in the visitor's browser, on their machine**. A client
clicking "Connect" is sent to their own laptop, where nothing is listening.

This is not a Google policy problem and verification does not fix it. It is what
`localhost` means. Public hosting comes first; everything below assumes it.

Google separately refuses `localhost` and bare IPs as redirect URIs on a
published app, so the two constraints point the same way.

---

## Decide this before you start

Hosting moves other people's Search Console data onto a machine you rent.
`docs/01-product-vision.md` §2 lists *"your client data never leaves this
machine"* as a product selling point, and `deploy/README.md` §1 flags the trade
already. Going multi-tenant with strangers also changes the severity of the bug
class this project has hit before: the 2026-08-06 cross-tenant leak was an
embarrassment on a laptop with one org in it. With real customers it is a
breach.

The isolation suite is the control. `deploy/update.sh` runs `tests/isolation`
before it serves traffic and refuses to deploy when `DATABASE_URL` is not the
`seoos_app` role. Do not weaken either.

---

## 1. Host it — `deploy/README.md` §1–4

Nothing public-specific. Oracle Always Free keeps `$0/month` literally true; a
domain is the only cost and it is annual.

Two guards in `deploy/update.sh` will stop you if `.env` is wrong:

- `API_URL` must be `https://` — the session cookie's `Secure` flag derives from
  its scheme.
- `WEB_URL` must equal `API_URL` — Caddy serves `/v1/*` and the web app from one
  hostname, and splitting them makes the browser drop the session cookie on
  every API call with no error in any log.

## 2. Fill in `apps/web/lib/company.ts`

Four values feed the homepage, the privacy policy and the terms:

| Field | Note |
|---|---|
| `domain` | Must match the domain you verify in Search Console |
| `legalName` | Must match the entity that verifies the domain |
| `contactEmail` | Must be monitored — deletion requests arrive here |
| `postalAddress` | **Ships as `TODO`.** Placeholder text is a rejection |

`SCOPES` in the same file is the single source for the per-scope justification
shown on `/` and `/privacy`. Reuse that wording verbatim in the verification
submission so the live pages and the paperwork cannot drift apart.

> The privacy policy and terms are an accurate draft written against what the
> code actually does — not legal advice. Have a lawyer read them.

## 3. Verify domain ownership

In **Search Console**, verify the domain, signed in as **the same Google account
that owns the Cloud project**. A mismatch here is the most common cause of a
verification submission bouncing without a useful reason.

## 4. Register the production redirect URIs

Both, in the Cloud project that issued the OAuth client:

```
https://<your-domain>/v1/auth/google/callback     ← sign-in
https://<your-domain>/v1/google/callback          ← Search Console / GA4 grant
```

`DEPLOY.md` §2 explains why the second is easy to miss: register only the first
and sign-in works perfectly, then connecting a property dies with
`redirect_uri_mismatch`. Keep the `localhost` pair registered too — they coexist
fine and you still want to run locally.

## 5. Switch to Production — this is the step that unblocks you

**Google Auth Platform → Audience → Publish app.**

You do not have to wait for verification to be useful. Unverified Production:

- anyone can connect, after clicking through a "Google hasn't verified this app"
  interstitial (*Advanced → Continue*)
- capped at 100 users
- **refresh tokens stop expiring after 7 days** — this is the real reason to
  leave Testing mode, and it is why the nightly sync survives

## 6. Submit for verification — removes the warning screen

Needs, on the verified domain and reachable without signing in:

- [ ] Homepage explaining the app — served at `/`
- [ ] Privacy policy with the Limited Use disclosure — served at `/privacy`
- [ ] App name and logo (brand verification)
- [ ] Unlisted YouTube demo showing the consent screen and each scope in use
- [ ] Written justification per scope — from `apps/web/lib/company.ts`

Budget weeks, with back-and-forth. `webmasters.readonly` and
`analytics.readonly` are **Sensitive**, not **Restricted**, so this is review
only — no third-party CASA security assessment, which is the five-figure one.

---

## What is already handled in code

Added 2026-08-06 while preparing for public access. Each is a property to
preserve, not just a feature that exists:

| | Where | Property |
|---|---|---|
| Open-redirect guard | `packages/core/urls.py` | `?redirect_to=` cannot leave the origin. Both OAuth callbacks concatenate onto `web_url`, so `.evil.com` and `@evil.com` used to walk off it — an open redirect on the end of a *real* Google login is a strong phishing primitive. Validated on the way in **and** the way out. |
| Rate limiting | `packages/core/ratelimit.py` | §27's limits are all per-session or per-org, which bounds nobody who has not signed in. Adds a per-IP bucket, since `/v1/auth/google/start` writes a row before any credential is checked. |
| Expiry sweep | `apps/worker/scheduler.py` `sweep_expired()` | `oauth_states` and `sessions` only shed rows on the happy path. Abandoned sign-ins accumulated forever, and anonymous callers can create them. |
| Public pages | `apps/web/app/{page,privacy,terms}` | `/` serves the homepage to logged-out visitors instead of redirecting to `/login` — a sign-in wall on the homepage is a documented rejection reason. |

## What is still open

- **No SSRF guard exists.** `packages/core/errors.py` defines `SSRFBlockedError`
  and nothing raises it; CLAUDE.md rule 9 has nothing to enforce. Not currently
  reachable — the crawler is Phase 2 and does not exist — but
  `POST /v1/google/connect` already stores a user-supplied domain as
  `start_url`. **Build the guard before the crawler dereferences that field**,
  or a signed-up stranger can point it at `169.254.169.254` and read the
  server's cloud metadata.
- **Rate-limit state is per-process.** `seoos-api.service` runs `--workers 2`,
  so a limit of N is effectively 2N, and a restart forgets every bucket. Fine
  for accident-shaped load and casual abuse; not a defence against a distributed
  attacker. That belongs at the edge — Caddy's `rate_limit` module or a CDN.
- **Error responses are not RFC 9457.** `docs/06-api-auth.md` §15 specifies
  Problem Details. The custom exception handlers in `apps/api/main.py` comply,
  but every plain `HTTPException` — most 401s, 403s and 404s — returns
  FastAPI's `{"detail": ...}` instead. Pre-existing and app-wide; unifying it
  changes response shapes the web app already reads, so it wants doing
  deliberately rather than as a side effect.
- **`scripts/build_pdf.py` has 30 ruff errors**, so `uv run ruff check .` is not
  clean repo-wide as CLAUDE.md claims. Everything under `packages/`, `apps/` and
  `tests/` passes.
