# Deploying to a server

The spec (§33) says "there is no CD" — the design target is one Mac, and the
`$0/month` constraint in `CLAUDE.md` assumes it. This directory is the escape
hatch for the one thing a laptop genuinely cannot do: **run when it is closed.**

Read `docs/11-costs.md` §40 before committing to this. The honest summary:

| | Local Mac | This |
|---|---|---|
| Recurring cost | $0 | $0 (Oracle free tier) or ~€4/mo (Hetzner) |
| Nightly sync at 02:00 IST | needs the lid open | unattended |
| Client data location | your machine | a rented machine |
| AI layer (Phase 2) | Metal GPU, fast | CPU only — see "The AI layer" below |

The third row is not a footnote. "Your client data never leaves this machine"
is one of the product's stated selling points (`docs/01-product-vision.md` §2,
Problem 7). Hosting moves it to someone else's machine. That may well be the
right trade for unattended syncing — but make it deliberately.

---

## 1. Pick a host

Both targets below are Ubuntu 24.04 LTS, arm64 or amd64. Everything here works
on either.

**Oracle Cloud — Always Free.** 4 Ampere A1 cores / 24 GB RAM, no expiry, $0.
The only mainstream host that keeps the `$0/month` claim literally true, and the
only one with enough RAM to attempt the Phase 2 AI layer on CPU. The catch is
real: A1 capacity in popular regions is frequently unavailable and can take
many attempts over several days. Set the region close to you, not to where
capacity is easiest.

**Hetzner — CAX11 (arm64) or CX22 (amd64).** Roughly €4/mo. Available
immediately, boringly reliable. This is what to use when the Oracle capacity
lottery has wasted enough of your time.

*Verify current specs and prices — both change.*

**Do not go below 4 GB RAM.** The worker pool runs 10 processes (~800 MB), the
Next.js build peaks well above idle, and `docs/11-costs.md` §42 identifies the
nightly sync window as the binding constraint. A 1 GB instance will thrash.

You also need a **domain name** pointed at the server's IP. Google OAuth will
not accept a bare IP as a redirect URI, so this is not optional.

---

## 2. Get the code onto the server

**This project is not currently a git repository.** There is no `.git`, so there
is nothing to clone. Deal with that first — `update.sh` is much less useful
without it, and §33's CI is specified against GitHub Actions anyway:

```bash
# On your Mac. .gitignore already excludes .env, data/, logs/, backups/, bin/ —
# check `git status` before the first push and confirm .env is not listed.
cd "/Users/kuldeep/Growleads AI SEO "
git init && git add -A && git commit -m "chore: initial commit"
gh repo create ai-seo-os --private --source=. --push
```

Then, on a fresh server as root:

```bash
apt-get update && apt-get install -y git
git clone <your-private-repo-url> /opt/seoos/app
/opt/seoos/app/deploy/bootstrap.sh seo.yourdomain.com you@yourdomain.com
```

If you would rather not use git, `rsync -av --exclude .env --exclude data
--exclude logs --exclude node_modules ./ root@server:/opt/seoos/app/` works, and
`update.sh` detects the absence of `.git` and skips the pull.

`bootstrap.sh` is idempotent — safe to re-run. It installs Docker, Caddy, Node 22
and uv; creates the `seoos` service user; installs the systemd units and the
firewall rules; and writes the Caddy config.

It deliberately starts nothing. Postgres, migrations and the build all need
`.env`, which does not exist yet — they live in `update.sh`.

### Why `/opt/seoos/app` and not a path with spaces

`CLAUDE.md` and `docs/10-deployment.md` §34 describe an ongoing fight with the
folder name `Growleads AI SEO ` — spaces plus a trailing space break `postgres`
and `pgserver` when they word-split unquoted paths, which is why `pgdata` lives
at `~/.seoos/pgdata` on the Mac. On the server the problem simply does not
exist. Keep it that way; do not clone into a path with spaces.

---

## 3. Configure

```bash
cp /opt/seoos/app/deploy/env.server.example /opt/seoos/app/.env
$EDITOR /opt/seoos/app/.env
```

Every value is annotated in that file. Five of them will ruin your day if you
get them wrong:

**`DATABASE_URL` must connect as `seoos_app`** — not `seoos` (the table owner)
and never `postgres` (superuser). RLS does not apply to a superuser under any
circumstances, and the dashboard query carries no `org_id` filter of its own
because RLS *is* the filter. Get this wrong and every organisation reads every
other organisation's clients, with no error and nothing in the logs. This is not
hypothetical — it was the live configuration on the Mac until 2026-08-06;
`tests/isolation/test_app_role.py` now fails loudly on it, and `update.sh`
refuses to deploy without it. `ADMIN_DATABASE_URL` is the owner, for Alembic
only, because `seoos_app` deliberately has no `CREATE`.

**`TOKEN_ENCRYPTION_KEY` — copy it from your Mac's `.env`.** Generating a fresh
one does not lose the database; it orphans every stored Google refresh token, so
every client has to reconnect. If you are migrating an existing database, this
key must come across with it.

**`SESSION_SECRET`** — copy it too, or every existing session is invalidated
(harmless, just a forced re-login).

**`API_URL` and `WEB_URL` must both be `https://your.domain`** — the same
origin, no port. Three things key off this:

- `cookie_secure` in `packages/core/config.py` derives the session cookie's
  `Secure` flag from `API_URL`'s scheme. It turns itself on at `https://`. This
  is the bug documented in `CLAUDE.md` — hardcoding it to `is_prod` made the
  browser silently drop the session.
- CORS in `apps/api/main.py` allows exactly `WEB_URL`.
- The session cookie is same-site only because Caddy serves the API and the web
  app from **one hostname**. Split them across two domains and the browser drops
  the cookie on every API call, with no error anywhere.

**`ENV=prod-local`** — this is the literal string `is_prod` compares against.
Anything else (`prod`, `production`) leaves the app in dev mode.

---

## 4. Start

Point your DNS at the server first — Caddy provisions the certificate on first
start and needs the name to resolve.

```bash
/opt/seoos/app/deploy/update.sh      # also the update path, every time
systemctl status seoos-api seoos-worker seoos-web
```

`update.sh` starts Postgres, rotates the `seoos_app` password to match
`DATABASE_URL` (`init.sql` hardcodes a dev one), runs migrations as the owner,
**runs `tests/isolation` before serving traffic**, builds the web bundle with
`API_URL` exported, and restarts everything. It refuses to run if `API_URL` is
not `https://` or `DATABASE_URL` is not the app role.

Then check health from *inside* the server — `/health` is deliberately not
exposed through Caddy:

```bash
curl -s localhost:8000/health | jq
```

---

## 5. Google Cloud

The single most likely thing to go wrong. In the project that issued the OAuth
client, register **both** redirect URIs — now with your real domain:

```
https://seo.yourdomain.com/v1/auth/google/callback     ← sign-in
https://seo.yourdomain.com/v1/google/callback          ← Search Console / GA4 grant
```

`DEPLOY.md` §2 explains why the second is easy to miss: register only the first
and sign-in works perfectly, then connecting a property dies with
`redirect_uri_mismatch`. Keep the `localhost` pair registered too — they coexist
fine, and you will still want to run locally.

Also confirm, per `DEPLOY.md`:

- **Google Search Console API** and **Google Analytics Data API** are enabled.
  Without them the OAuth grant succeeds and every sync then returns 403.

### Publishing status — pick one deliberately

| Status | Who can connect | Cost |
|---|---|---|
| **Testing** | Only emails listed under *Test users*, max 100 | — |
| **Production, unverified** | Anyone, after clicking through a warning screen. Capped at 100 users | — |
| **Production, verified** | Anyone, no warning | Weeks of review |

**Testing mode issues refresh tokens that expire after 7 days.** This is the
detail that matters most here and it is easy to miss, because nothing fails at
first. Every stored Google connection stops working about a week after it is
made, and the nightly sync then fails with a 403 that looks like a Search
Console permissions problem rather than an auth-mode one. Do not run a real
deployment in Testing mode.

**Verification requires all of the following**, and the redirect URIs must be
`https://` on a domain you own — `localhost` is rejected outright:

- A publicly reachable homepage on the verified domain that explains the app.
  Served at `/` by `apps/web/components/marketing-home.tsx`; it must not
  redirect to a sign-in wall, which is why `apps/web/app/page.tsx` renders it
  for logged-out visitors rather than bouncing them to `/login`.
- A privacy policy on the same domain containing the Limited Use disclosure.
  Served at `/privacy`.
- Domain ownership verified in Search Console, under the same Google account
  that owns the Cloud project.
- A demo video (unlisted YouTube is fine) showing the consent screen and each
  scope being used.
- A written justification per scope. `apps/web/lib/company.ts` holds the ones
  the homepage and privacy policy display — reuse that wording so the
  submission and the live pages cannot drift apart.

The scopes this app requests — `webmasters.readonly` and `analytics.readonly` —
are classed **Sensitive**, not **Restricted**. That distinction is worth real
money: Restricted scopes (Gmail, Drive) additionally require an annual
third-party CASA security assessment. Sensitive scopes require review only.

**Fill in `apps/web/lib/company.ts` before submitting.** It ships with a
`TODO` postal address, and placeholder text on the privacy policy is a
rejection.

---

## 6. What runs unattended

`apps/worker/scheduler.py` ticks every 60 seconds; a Postgres advisory lock
means only one worker process evaluates any given pass.

Keep the **server clock in UTC**. The scheduler converts to `Asia/Kolkata`
itself, and that conversion is the thing it exists to get right — it was
verified end to end on 2026-08-06 (`next_run_at` advanced to 20:30 UTC = 02:00
IST). Setting the system timezone to IST does not help and invites a
double-conversion bug.

Backups run daily at 03:30 UTC via `seoos-backup.timer` into
`/opt/seoos/backups`, keeping the last 14. **They are on the same disk as the
database, which is not a backup.** Copy them off the box — that part is left to
you deliberately, because where they go is your decision:

```bash
systemctl list-timers seoos-backup
```

---

## 7. The AI layer

`packages/ai/` does not exist yet, so nothing here installs Ollama and the
`OLLAMA_*` values in `.env` are inert. When you build Phase 2
(`docs/07-ai-architecture.md`), this deployment hits the wall §40 describes:

> **The GPU line is what makes hosted local-AI uneconomic at small scale.**

No cloud host at €4/mo has a GPU. `docs/10-deployment.md` §32 measured CPU
inference for a 9B model at **8–15× slower** than Metal — a 4-second call
becomes 45 seconds, which makes the Chat Assistant unusable and turns the
nightly AI budget per site (§39) into something that no longer fits the window.

Three honest options, in the order I would consider them:

1. **Split the deployment.** Pipeline on the server, AI on the Mac — the server
   enqueues `ai` jobs and a worker on your Mac (`--queues ai`) drains them over
   a tunnel. Keeps Metal, keeps $0, adds a moving part. The queue is already
   designed for this: leases and a reclaimer mean a worker that vanishes
   mid-job is handled.
2. **`RemoteProvider` with your own key.** The adapter already exists behind
   `LLMProvider`. This is a paid service in a default path — `CLAUDE.md` rule 1
   — so it is a real architectural decision, not a config change.
3. **Accept slow.** Reports generate overnight; nobody is watching. Only the
   Chat Assistant genuinely needs interactive latency.

Do not pick a host based on Phase 2 until you have measured Phase 2.

---

## 8. Rolling back

`update.sh` does not snapshot the database. Before a migration you are unsure
about:

```bash
sudo -u seoos /opt/seoos/app/backup.sh
```

To roll the code back, `git checkout <sha>` and re-run `update.sh`. Alembic
downgrades are not automatic and several migrations in this schema are not
reversible — partitioning and RLS policy changes especially.
