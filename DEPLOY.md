# Going live

Data pipeline only — GSC + GA4 → dashboards, synced nightly. The AI layer
(`packages/ai/`, report generator, Ollama) is not built yet, so there is nothing
to install for it and nothing that needs a model.

Everything runs on this machine. `$0/month` recurring, as specified.

---

## 1. Keys

**No new keys are needed.** `.env` is already complete:

| Variable | State |
|---|---|
| `DATABASE_URL`, `POSTGRES_PASSWORD` | set — bundled Postgres 16.2 + pgvector |
| `TOKEN_ENCRYPTION_KEY`, `SESSION_SECRET` | generated |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | set |
| `APIFY_TOKEN`, `REMOTE_LLM_API_KEY` | **intentionally blank** |

The last two are paid adapters behind `SerpProvider` / `LLMProvider`. Leave them
blank. Filling either one puts a subscription in a default code path, which
`CLAUDE.md` rule 1 forbids.

> **Back up `TOKEN_ENCRYPTION_KEY` somewhere outside this folder.** Losing it
> does not lose the database — it orphans every stored Google connection, and
> every client has to reconnect.

---

## 2. Google Cloud — the part that is not a key

In the Google Cloud project that issued the OAuth client:

- [ ] Enable **Google Search Console API**
- [ ] Enable **Google Analytics Data API**
- [ ] OAuth consent screen → add **every** Google account you will sign in with
      under **Test users** — not just `anuj@growleadsagency.com`. An account
      that is not on the list gets `Error 403: access_denied` with
      *"has not completed the Google verification process"*, which reads like a
      code fault and is not one.
- [ ] Know what Testing mode costs you: **refresh tokens expire after 7 days.**
      Nothing fails at first. About a week after each client connects, the
      nightly sync starts returning 403 and it looks like a Search Console
      permissions problem. Fine for a local trial, wrong for anything real —
      see `deploy/README.md` §5 for the Production and verification paths.
- [ ] Understand that `localhost` cannot serve other people. The redirect URI
      resolves in *the visitor's* browser, so a client clicking "Connect" is
      sent to their own machine, where nothing is listening. Letting anyone
      connect requires public HTTPS hosting first — Google verification does
      not change this, and will not accept a `localhost` redirect URI anyway.
- [ ] Register **both** authorised redirect URIs:

      http://localhost:8000/v1/auth/google/callback     ← sign-in
      http://localhost:8000/v1/google/callback          ← Search Console / GA4 grant

The second URI is easy to miss. The spec's §60 checklist lists only the first,
but `apps/api/routers/google.py` requests the data scopes on its own callback.
Register only the sign-in URI and login works fine — then connecting a property
fails with `redirect_uri_mismatch`.

Without the two APIs enabled, the OAuth grant succeeds and every sync then
returns 403.

- [ ] Confirm your Google account has Search Console access to at least one real
      client property. Nothing downstream can be tested without it.

---

## 3. Start it

```bash
./run.sh --prod     # built bundle, JSON logs, no reloader
```

Dashboard on `http://localhost:3000`, API on `:8000`.

Two things differ from `./run.sh`:

- Logs go to `logs/app.log` as JSON, **not** to the terminal. `tail -f logs/app.log`
  to watch.
- `/demo` returns 404 on purpose — URL sign-in is a dev-only affordance.

Use `./run.sh` (dev) if you want the demo link and console logs.

---

## 4. Connect a real client

1. Sign in with Google at `http://localhost:3000`.
2. Go to `/connect` and grant the Search Console + Analytics scopes.
3. Pick the property, name the client, connect.

That enqueues a backfill of up to 16 months **and** creates the nightly
schedules. The dashboard fills in as data lands.

Check progress:

```bash
curl -s localhost:8000/v1/google/sites/<site_id>/status | jq
```

---

## 5. What runs unattended

`apps/worker/scheduler.py` ticks every 60 seconds. Every worker process ticks;
a Postgres advisory lock means only one actually evaluates any given pass.

- `gsc_sync` and `ga4_sync`, nightly at **02:00 Asia/Kolkata**, per connected site.
- Each site gets a deterministic offset of 0–239 minutes derived from its UUID,
  so fifteen sites do not all hit Google at 02:00 and get the IP throttled. The
  same site lands in the same slot every night.
- A sync chains a `refresh_views` job, so the materialised views behind the
  dashboard are never refreshed on a page request.
- Laptop closed for three days → **one** catch-up run per schedule on wake, not
  three. `next_run_at` is always recomputed forward from `now()`.

Nothing needs to be running at 02:00 except this machine, awake, with `./run.sh`
going. There is no cron entry and no launchd plist — closing the laptop just
delays the sync to the next tick after it wakes.

---

## 6. Backups

```bash
./backup.sh     # db + data + .env → one archive
```

The database lives at `~/.seoos/pgdata`, deliberately outside this folder —
Postgres word-splits the unquoted path and the folder name has spaces.
`backup.sh` captures it via `pg_dump` regardless of location.

---

## Health check

```bash
curl -s localhost:8000/health | jq
```

```json
{"ok": true, "checks": {"postgres": {"ok": true, "version": "16.2", "pgvector": true},
                        "google_oauth": {"configured": true}}}
```

## Before any commit touching data access

```bash
uv run pytest tests/isolation
```
