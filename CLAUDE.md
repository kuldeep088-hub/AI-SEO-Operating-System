# AI SEO Operating System

Local-first SEO platform for Growleads Agency. **$0/month recurring cost is a hard
constraint, not a preference.**

## Before you write code

`docs/` is the specification. Read the relevant section first.

| Working on | Read |
|---|---|
| Schema, queries, migrations | `docs/05-database.md` |
| Endpoints, auth, RBAC | `docs/06-api-auth.md` |
| Agents, prompts, RAG, embeddings | `docs/07-ai-architecture.md` |
| Jobs, queue, crawler limits, tenancy | `docs/08-infrastructure.md` |
| Security, logging, monitoring | `docs/09-security-ops.md` |
| Stack decisions and rationale | `docs/10-deployment.md` §36–37 |
| UI layout and screens | `docs/04-ui-ux.md` |
| What to build next | `docs/12-roadmap.md` §45 |

## Hard rules — violating these is a bug, not a style preference

1. **No paid service in a default code path.** Paid services exist only behind the
   `SerpProvider` / `LLMProvider` adapters in `packages/core/providers.py`, off by default.
   About to add a dependency with a subscription? Stop.
2. **`org_id` on every tenant table, RLS policy on every tenant table.** No exceptions.
3. **Every tenant query goes through `tenant_tx()`** (Python) or `tenantQuery()` (TS).
   Never query a tenant table on a bare connection.
4. **Prompts live in `prompt_versions`, never in Python string literals.**
5. **`think=False` for structured AI calls.** Reasoning on is ~30× slower and buys nothing
   when output is schema-constrained (measured 27s → 0.8s in Growleads L.S). Only the Report
   Narrator, Chat, and Action Plan agents set it on.
6. **Never let the model compute a number.** Compute in SQL, pass it in, ask the model to
   explain it.
7. **Never state a cause without evidence.** Reports and chat say "X happened, and Y occurred
   on the same date" — never "X happened because of Y."
8. **Domain logic goes in `packages/`.** `apps/api` and `apps/worker` both import it. Never
   duplicate logic between them.
9. **Every external fetch goes through the SSRF guard.** No bare `httpx.get` on a URL that
   came from a user, a sitemap, or a crawled page.
10. **Secrets are never logged.** Redaction is a structlog processor — don't bypass it.
11. **New dependency requires a one-line justification** in the commit message.

## Commands

> **Paths with spaces.** This folder's name contains spaces and a trailing space, which
> breaks `postgres` and `pgserver` when they word-split unquoted paths. `setup.sh` and
> `run.sh` set `UV_PROJECT_ENVIRONMENT=~/.seoos/venv` and keep `pgdata` at `~/.seoos/pgdata`
> to avoid it. If you run commands by hand, export that variable first. See docs §32.

```bash
./setup.sh                      # install / update everything (idempotent)
python scripts/pg.py start      # Postgres: docker if present, bundled if not
python scripts/pg.py status
python scripts/seed_demo.py     # demo data + a session cookie, for looking around
python scripts/seed_demo.py --clear
./run.sh                        # start everything, Ctrl-C stops all
./run.sh --prod                 # production mode (built, not dev server)
./backup.sh                     # db + data + .env → one archive
./serve-docs.sh                 # read the spec at localhost:4000

uv run pytest                   # all Python tests
uv run pytest tests/isolation   # ← run before any commit touching data access
uv run ruff check . && uv run mypy packages apps/api
uv run alembic upgrade head
uv run alembic revision -m "..."

cd apps/web && npm run dev      # web only
cd apps/web && npm run typecheck
```

## Conventions

- **Python**: Ruff (line 100), mypy strict on `packages/`, async throughout
- **SQL**: hand-written for analytics; raw SQL in migrations (this schema uses partitioning,
  RLS, generated columns, and pgvector — an ORM obscures all four)
- **TypeScript**: strict, no `any`
- **Tests**: real Postgres, never SQLite or mocks for database behaviour
- **Commits**: conventional commits, referencing the doc section implemented

## Current state

**Phase 0 complete and verified** — 49 tables, 29 RLS-protected, 31 policies, both
materialised views, HNSW index. Google OAuth, opaque sessions, RBAC. Dashboard renders real
KPIs from `mv_site_kpis` through a tenant-scoped RSC query. 32/32 isolation tests pass;
ruff, mypy strict, and `tsc` all clean.

Two RLS bugs were caught by the isolation suite during Phase 0 and are fixed in migration
0001 — worth knowing about because both are easy to reintroduce:
1. `current_setting(..., true)` returns `''` (not NULL) after a transaction-scoped
   `set_config`, and `''::uuid` **raises**. Every policy uses `nullif(..., '')::uuid` so it
   fails closed instead of erroring.
2. Permissive policies are **OR'd**. The `client_viewer` scope had to be `AS RESTRICTIVE`,
   or a second permissive policy would have *widened* access rather than narrowed it.

**Phase 1 data pipeline is in place and running.** GSC + GA4 OAuth grant, property discovery,
backfill and incremental sync, the `jobs` queue with leases and a reclaimer, and the cron
scheduler (`apps/worker/scheduler.py`). 55 tests pass; ruff, mypy (`packages apps/api`), and
`tsc` are clean; `./run.sh --prod` builds and serves.

Verified end to end on 2026-08-06: a due schedule fired, enqueued `refresh_views` on the
`default` queue at priority 100, the worker ran it, and `next_run_at` advanced to 20:30 UTC —
02:00 Asia/Kolkata, the timezone conversion the scheduler exists to get right.

Three bugs found and fixed while wiring the scheduler, all easy to reintroduce:
1. `enqueue` caught `UniqueViolationError` and returned None. Catching it does **not**
   un-poison the transaction — Postgres aborts the whole block, so one site with a pending
   job silently cancelled every other site's nightly sync, and a double-clicked "Connect"
   aborted the tenant transaction. Now `ON CONFLICT … DO NOTHING`, which never raises.
2. The session cookie's `Secure` flag came from `is_prod`. Production here is still
   localhost over http, so `./run.sh --prod` would have made the browser silently drop the
   session — login failing with no error anywhere. Now derived from `API_URL`'s scheme.
3. `next build` runs ESLint and rejected two `<a href="/">` navigations, so `--prod` did not
   build at all. `tsc --noEmit` passes them — typecheck is not a substitute for the build.

**A cross-tenant leak was found and fixed on 2026-08-06**, while writing the server
deployment. Worth reading in full, because the shape of it is the one this project is
most likely to reproduce.

`scripts/pg.py start()` returned `srv.get_uri(...)` — the bundled server's **superuser**
URI — and `run.sh` exported it as `DATABASE_URL` for the API, the worker and the web app.
RLS never applies to a superuser, `FORCE` or not, so every policy in migration 0001 was
inert at runtime. The dashboard query in `apps/web/app/page.tsx` carries no `org_id`
filter by design — RLS *is* the filter — so a user whose org owned no sites was served
every other org's clients. Verified by signing in and reading the page, not by reasoning.

Three things about why it survived:

1. **32/32 isolation tests passed the whole time.** `tests/conftest.py` rewrites the URL
   to `seoos_app` before testing. It proved the *policies* were right; nothing checked
   what role the *application* connects as. `tests/isolation/test_app_role.py` now does,
   and fails loudly if `DATABASE_URL` is superuser or `BYPASSRLS`.
2. **There are now three database URLs, and the distinction is load-bearing.**
   `DATABASE_URL` is `seoos_app` (API + web, RLS enforced). `ADMIN_DATABASE_URL` is the
   owner (Alembic only — `seoos_app` has no `CREATE`). `settings.worker_database_url` is
   privileged on purpose: the queue claims jobs with `SKIP LOCKED` across every org and
   `scheduler.tick()` scans all due schedules in one pass, so under the app role both
   return zero rows and the nightly sync stops firing **silently**. Job handlers are
   therefore responsible for entering `tenant_tx()` themselves.
3. `infra/postgres/init.sql` hardcodes `seoos_app`'s password. Fine on a laptop; on a
   server `deploy/update.sh` rotates it to match `DATABASE_URL` on every run.

**Next: the AI layer** (`docs/07-ai-architecture.md`) — there is no `packages/ai/` yet, so
Ollama is not installed and no report is generated. Phase 1's exit criterion, a monthly
report for a real client, is not met.

## The thing most likely to go wrong

Plausible code that doesn't match the spec — a queue without the lease sweep, an RLS policy
missing the `client_viewer` branch, a crawler without conditional requests. Each looks right,
passes a basic test, and quietly loses a property the design depends on.

Cite the doc section in the prompt, and verify the specific property it calls out — not just
that the feature works.
