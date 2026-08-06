# 10 — Deployment

Sections §32–§37. [← Back to index](../README.md)

---

## §32. Deployment Architecture

### One machine, five processes

```
┌─────────────────────────── Apple M5 · 16 GB ───────────────────────────┐
│                                                                        │
│  ┌── Docker ──────────────────────────────────────────────────────┐    │
│  │  postgres:16 + pgvector      127.0.0.1:5432    ~1.5 GB         │    │
│  │  (optional) prometheus + grafana               ~300 MB         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  ┌── Native (not containerised — see below) ──────────────────────┐    │
│  │  ollama serve                127.0.0.1:11434   ~6 GB resident  │    │
│  │  next dev/start              127.0.0.1:3000    ~400 MB         │    │
│  │  uvicorn (FastAPI)           127.0.0.1:8000    ~250 MB         │    │
│  │  worker pool (10 procs)      —                 ~800 MB         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                        │
│  Total resident ≈ 9.5 GB · headroom ≈ 6.5 GB                           │
└────────────────────────────────────────────────────────────────────────┘
```

### Why Ollama is not in Docker

The most important deployment decision, and the least obvious.

**Docker Desktop on macOS runs containers inside a Linux VM, and that VM has no access to the
Apple GPU.** Ollama in a container falls back to CPU inference — roughly 8–15× slower for a
9B model. A 4-second inference becomes 45 seconds, and the Chat Assistant becomes unusable.

Ollama runs natively, uses Metal, and the app connects to `host.docker.internal:11434` from
containers or `localhost:11434` natively.

**Corollary: the app services also run natively.** Once Ollama is outside Docker, putting
FastAPI and the worker inside buys nothing — they'd cross the VM network boundary to reach
both Ollama and (if it were native) Postgres. Only Postgres is containerised, because it
benefits from isolation and has no GPU or host-network requirement.

This is a macOS-specific decision. §42 notes that a Linux deployment can containerise
everything, since Linux Docker uses the host kernel directly.

### The two scripts

Following the `Growleads L.S` pattern exactly — one script to install, one to run.

**`setup.sh`** — idempotent, safe to re-run, no sudo:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1;32m▸\033[0m %s\n" "$1"; }
need() { command -v "$1" >/dev/null || { echo "Missing: $1 — $2"; exit 1; }; }

step "Checking prerequisites"
need docker  "install Docker Desktop from docker.com"
need node    "install Node 20+ from nodejs.org or via nvm"
need python3 "macOS ships python3; if missing, install Xcode CLT"
docker info >/dev/null 2>&1 || { echo "Docker is installed but not running."; exit 1; }

step "Locating Ollama (no sudo, no Homebrew)"
# Ollama.app installs to ~/Applications and is NOT added to PATH.
# Resolve it explicitly and symlink into ./bin — same approach as Growleads L.S.
APP_OLLAMA="$HOME/Applications/Ollama.app/Contents/Resources/ollama"
if command -v ollama >/dev/null; then
  OLLAMA="$(command -v ollama)"
elif [ -x "$APP_OLLAMA" ]; then
  OLLAMA="$APP_OLLAMA"
else
  curl -fsSL https://ollama.com/download/Ollama-darwin.zip -o /tmp/ollama.zip
  unzip -q -o /tmp/ollama.zip -d "$HOME/Applications"
  OLLAMA="$APP_OLLAMA"
fi
mkdir -p bin && ln -sf "$OLLAMA" bin/ollama
echo "  ollama → $OLLAMA"

step "Pulling models (~5.8 GB — resumable)"
"$OLLAMA" pull qwen3.5:9b
"$OLLAMA" pull nomic-embed-text

step "Starting Postgres"
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -q; do sleep 1; done

step "Writing .env"
if [ ! -f .env ]; then
  cp .env.example .env
  python3 - <<'PY' >> .env
from cryptography.fernet import Fernet
import secrets
print(f"TOKEN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"SESSION_SECRET={secrets.token_urlsafe(48)}")
PY
  echo "  Generated encryption keys. Keep .env safe — losing it orphans OAuth tokens."
else
  echo "  .env exists — leaving it alone."
fi

step "Installing dependencies"
(cd apps/web && npm ci)
uv sync

step "Running migrations"
uv run alembic upgrade head

step "Seeding prompts"
uv run python -m packages.agents.seed_prompts

printf "\n\033[1;32m✓ Setup complete.\033[0m  Run ./run.sh\n"
```

**`run.sh`** — starts everything, one Ctrl-C stops it all:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

cleanup() { echo; echo "Stopping…"; kill 0; docker compose stop postgres; }
trap cleanup EXIT INT TERM

docker compose up -d postgres

# ./bin/ollama is the symlink written by setup.sh — Ollama.app is not on PATH.
OLLAMA="./bin/ollama"
[ -x "$OLLAMA" ] || { echo "Run ./setup.sh first (bin/ollama missing)."; exit 1; }
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  "$OLLAMA" serve &
  until curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; do sleep 0.3; done
fi

uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
uv run python -m apps.worker.main &
(cd apps/web && npm run dev) &

echo
echo "  Dashboard   http://localhost:3000"
echo "  API docs    http://localhost:8000/v1/docs"
echo "  Ctrl-C to stop everything."
wait
```

`trap cleanup EXIT` with `kill 0` kills the whole process group. Without it, Ctrl-C leaves
orphaned uvicorn and worker processes holding ports — the most common local-dev annoyance and
trivially avoidable.

### Environments

| Environment | Purpose | Differences |
|---|---|---|
| `dev` | Daily work | Next dev server (HMR), verbose logging, seeded demo data available |
| `prod-local` | real client data | `next build && next start`, JSON logs, real OAuth credentials |

`prod-local` is the deployment that matters. `NODE_ENV=production` plus `next build` roughly
halves memory and makes page loads noticeably faster — worth it for something used daily.

```bash
./run.sh --prod        # builds, then starts in production mode
```

### First-run and update

```bash
# First time
git clone … && cd "Growleads AI SEO" && ./setup.sh && ./run.sh

# Updating
git pull && ./setup.sh && ./run.sh        # setup.sh is idempotent
```

`setup.sh` doubles as the update path — it re-runs migrations, installs new dependencies, and
skips anything already done.

---

## §33. CI/CD

### There is no CD

Nothing to deploy to. "Deployment" is `git pull && ./setup.sh`. CI exists to keep the codebase
honest, and it runs on GitHub Actions' free tier.

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  python:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_PASSWORD: postgres }
        options: >-
          --health-cmd pg_isready --health-interval 10s --health-retries 5
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy packages apps
      - run: uv run alembic upgrade head
        env: { DATABASE_URL: postgresql://postgres:postgres@localhost/postgres }
      - run: uv run pytest -v --cov=packages --cov=apps --cov-fail-under=70
        env: { DATABASE_URL: postgresql://postgres:postgres@localhost/postgres }
      - run: uv run pip-audit --strict

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: apps/web/package-lock.json }
      - run: cd apps/web && npm ci
      - run: cd apps/web && npm run lint
      - run: cd apps/web && npx tsc --noEmit
      - run: cd apps/web && npm run build
      - run: cd apps/web && npm audit --audit-level=high

  tenant-isolation:
    runs-on: ubuntu-latest
    # The most important job in CI — see §28, §48
    services:
      postgres: { image: pgvector/pgvector:pg16, env: { POSTGRES_PASSWORD: postgres },
                  ports: ["5432:5432"] }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run alembic upgrade head
      - run: uv run pytest tests/isolation -v --tb=short
        env: { DATABASE_URL: postgresql://postgres:postgres@localhost/postgres }
```

**`tenant-isolation` is a separate job on purpose.** It iterates every API route with a
mismatched-tenant principal and asserts 403-or-empty. Separating it means a red CI badge tells
you immediately whether the failure is a lint nit or a data-leak regression.

### AI eval workflow

Runs only when prompts change — model inference in CI is slow, and prompts are the thing that
silently regresses (§18):

```yaml
# .github/workflows/evals.yml
on:
  pull_request:
    paths: ['packages/agents/prompts/**', 'packages/agents/evals/**']
jobs:
  evals:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: curl -fsSL https://ollama.com/install.sh | sh
      - run: ollama pull qwen3.5:9b     # ~4 min, cached between runs
      - run: uv run python -m packages.agents.evals.run --compare-to main
      # Fails if any agent scores below its current baseline
```

### The static tools site

The only thing that genuinely deploys anywhere (§44). Cloudflare Pages, free tier, no backend:

```yaml
# .github/workflows/tools-site.yml
on:
  push:
    branches: [main]
    paths: ['apps/tools-site/**']
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd apps/tools-site && npm ci && npm run build
      - uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CF_API_TOKEN }}
          accountId: ${{ secrets.CF_ACCOUNT_ID }}
          projectName: ai-seo-tools
          directory: apps/tools-site/dist
```

### Pre-commit

Catches the cheap failures before they reach CI:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff, args: [--fix] }, { id: ruff-format }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: detect-private-key
      - id: check-merge-conflict
  - repo: local
    hooks:
      - id: no-env-commit
        name: block .env
        entry: bash -c '! git diff --cached --name-only | grep -qE "^\.env$"'
        language: system
```

The `.env` block matters more than it looks — that file contains `TOKEN_ENCRYPTION_KEY`, and
committing it once means rotating every OAuth connection.

---

## §34. Docker Architecture

### What is containerised, and what isn't

| Service | Container? | Why |
|---|---|---|
| Postgres | **Yes, when Docker is present** | Isolation, easy version pinning, no host install |
| Prometheus / Grafana | Yes, optional profile | Off unless wanted |
| Ollama | **No** | Needs Metal GPU access (§32) |
| FastAPI / worker / Next.js | **No** | Would cross the VM boundary to reach Ollama and Postgres |

### When Docker isn't available

Docker Desktop needs a GUI install and, on managed machines, admin rights. A tool that
cannot start is a tool nobody uses, so `scripts/pg.py` detects Docker and falls back to
**`pgserver`** — PostgreSQL 16 and pgvector shipped as a pip package. No daemon, no sudo, no
container runtime.

```bash
python scripts/pg.py start     # docker compose if available, else bundled binaries
python scripts/pg.py status
python scripts/pg.py psql
```

The application cannot tell the difference: same major version, same extension, same SQL.
Two differences are worth knowing:

| | Docker image | Bundled `pgserver` |
|---|---|---|
| Extensions | `pgcrypto`, `pg_trgm`, `btree_gin`, `citext`, `vector` | **`vector` only** |
| Data directory | Docker named volume | `~/.seoos/pgdata`, symlinked from `data/pgdata` |

**The schema depends on neither.** `gen_random_uuid()` and `sha256()` are core in Postgres 16,
so `pgcrypto` is never needed; `citext` is replaced by a unique index on `lower(email)`; and
the `pg_trgm` trigram index is created only when the extension exists. Migration `0001` probes
for each optional extension and skips what it can't create.

### Paths with spaces — a real constraint on this machine

This project lives at `/Users/kuldeep/Growleads AI SEO ` — spaces, plus a trailing space.
Several tools word-split unquoted paths and break on it:

| Tool | Failure |
|---|---|
| `postgres` | Socket dir arrives inside a `-o` options string → `invalid argument: "AI"` |
| `pgserver` | Invokes `psql` through a shell without quoting → exit 127 |

Both are avoided by keeping two things on space-free paths, which `setup.sh` and `run.sh` do
automatically:

```bash
export UV_PROJECT_ENVIRONMENT="$HOME/.seoos/venv"   # the virtualenv
# pgdata lives at ~/.seoos/pgdata, symlinked from data/pgdata
```

Putting `pgdata` outside the project is not a departure from the Docker setup — a Docker
named volume also lives outside the folder. `backup.sh` captures it either way via `pg_dump`.

**If you would rather not carry this workaround, renaming the folder to `Growleads-AI-SEO`
removes the whole class of problem.**

### `docker-compose.yml`

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16@sha256:...      # digest-pinned, §29
    container_name: seoos-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: seoos
      POSTGRES_USER: seoos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_INITDB_ARGS: "--data-checksums"
    ports:
      - "127.0.0.1:5432:5432"        # ← NOT "5432:5432". See §29.
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/10-init.sql:ro
    command:
      - postgres
      - -c=shared_buffers=1GB
      - -c=effective_cache_size=3GB
      - -c=work_mem=32MB
      - -c=maintenance_work_mem=512MB
      - -c=max_connections=60
      - -c=random_page_cost=1.1              # SSD
      - -c=effective_io_concurrency=200
      - -c=max_parallel_workers_per_gather=4
      - -c=log_min_duration_statement=1000   # log queries over 1s
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U seoos -d seoos"]
      interval: 10s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits: { memory: 2G }

  prometheus:
    image: prom/prometheus:latest
    profiles: [metrics]
    ports: ["127.0.0.1:9090:9090"]
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - promdata:/prometheus

  grafana:
    image: grafana/grafana:latest
    profiles: [metrics]
    ports: ["127.0.0.1:3001:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafanadata:/var/lib/grafana

volumes:
  pgdata:
  promdata:
  grafanadata:
```

**Tuning notes.** `shared_buffers=1GB` and `effective_cache_size=3GB` are sized for a 16 GB
machine already holding a 6 GB model — Postgres's defaults (128 MB) would make the 33M-row
`gsc_daily` table painfully slow, while the usual "25% of RAM" advice would starve Ollama.
`work_mem=32MB` × 60 connections is a 1.9 GB worst case, which the 2 GB limit contains.

`--data-checksums` catches silent corruption, which matters on a laptop that gets closed
mid-write.

### The Dockerfile that does exist

For a Linux server deployment (§42) — unused locally but kept working so the path stays open:

```dockerfile
# infra/Dockerfile.api
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY packages ./packages
COPY apps/api ./apps/api
RUN useradd -u 10001 -m app && chown -R app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c \
  "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn","apps.api.main:app","--host","0.0.0.0","--port","8000"]
```

Multi-stage so the runtime image excludes build tooling; non-root user; healthcheck.

---

## §35. Folder Structure

```
Growleads AI SEO/
├── README.md
├── docs/                            ← this documentation
├── setup.sh                         ← install everything, idempotent
├── run.sh                           ← start everything, Ctrl-C stops all
├── backup.sh                        ← pg_dump + data/ + .env → one archive
├── serve-docs.sh
├── docker-compose.yml
├── pyproject.toml                   ← uv workspace root
├── uv.lock
├── .env.example
├── .gitignore                       ← .env, data/, logs/, backups/
│
├── apps/
│   ├── web/                         Next.js 15 dashboard
│   │   ├── app/
│   │   │   ├── (auth)/login/
│   │   │   ├── (app)/
│   │   │   │   ├── page.tsx                    cross-client dashboard
│   │   │   │   ├── action-plan/
│   │   │   │   ├── clients/
│   │   │   │   ├── s/[site]/                   site-scoped modules
│   │   │   │   │   ├── page.tsx                site dashboard
│   │   │   │   │   ├── search-console/
│   │   │   │   │   ├── technical/
│   │   │   │   │   ├── keywords/
│   │   │   │   │   ├── content/
│   │   │   │   │   ├── linking/
│   │   │   │   │   ├── chat/
│   │   │   │   │   └── reports/
│   │   │   │   └── settings/
│   │   │   ├── portal/[token]/                 client read-only view
│   │   │   └── onboarding/
│   │   ├── components/
│   │   │   ├── ui/                             shadcn primitives
│   │   │   ├── charts/
│   │   │   └── domain/                         KpiCard, IssueList, ClusterTable…
│   │   ├── lib/
│   │   │   ├── db.ts                           RSC direct Postgres reads
│   │   │   ├── api.ts                          typed client (generated)
│   │   │   └── types.gen.ts                    ← from OpenAPI, do not edit
│   │   └── package.json
│   │
│   ├── api/                         FastAPI
│   │   ├── main.py
│   │   ├── deps.py                             Principal, RBAC, RLS session vars
│   │   ├── middleware.py                       request_id, logging, errors
│   │   ├── health.py
│   │   └── routers/
│   │       ├── auth.py  clients.py  sites.py
│   │       ├── gsc.py   ga4.py      technical.py
│   │       ├── keywords.py  content.py  linking.py
│   │       ├── chat.py  reports.py  jobs.py
│   │       └── webhooks.py
│   │
│   ├── worker/                      job runner
│   │   ├── main.py                             pool + queue assignment
│   │   ├── runner.py                           dequeue, lease, retry, heartbeat
│   │   ├── scheduler.py                        cron → enqueue
│   │   └── jobs/
│   │       ├── gsc_sync.py  ga4_sync.py
│   │       ├── crawl_site.py  diff_crawl.py  lighthouse_run.py
│   │       ├── embed_pages.py  cluster_keywords.py
│   │       ├── analyse_issues.py  suggest_links.py
│   │       ├── generate_draft.py
│   │       ├── weekly_report.py  monthly_report.py
│   │       └── prune_storage.py  refresh_views.py  create_partitions.py
│   │
│   └── tools-site/                  static free tools (§44) → Cloudflare Pages
│       ├── src/                                schema generator, robots tester, …
│       └── package.json
│
├── packages/                        shared Python — imported by api AND worker
│   ├── core/
│   │   ├── config.py  logging.py  crypto.py
│   │   ├── errors.py                           Transient/Quota/Permanent
│   │   ├── providers.py                        LLMProvider, SerpProvider (§17, §27)
│   │   └── quota.py                            persisted token buckets
│   ├── db/
│   │   ├── engine.py  models.py  repositories/
│   │   └── migrations/                         alembic
│   ├── integrations/
│   │   ├── google/  (gsc.py ga4.py gbp.py ads.py oauth.py)
│   │   ├── wordpress.py  wikidata.py
│   │   ├── lighthouse.py                       local CLI wrapper
│   │   └── serp/  (local_scraper.py  apify.py)
│   ├── crawler/
│   │   ├── crawler.py  parser.py  robots.py
│   │   ├── ssrf.py                             §29 guard
│   │   └── rules/                              one module per issue rule
│   ├── analysis/
│   │   ├── clustering.py  linking.py  entities.py
│   │   ├── opportunity.py  health.py  diff.py
│   └── agents/
│       ├── runtime.py                          Ollama client, schema enforcement
│       ├── graphs/                             LangGraph per agent
│       ├── prompts/                            seed data → prompt_versions
│       ├── schemas.py                          output JSON schemas
│       └── evals/                              cases.jsonl + rubrics (§18)
│
├── infra/
│   ├── Dockerfile.api  Dockerfile.worker
│   ├── postgres/init.sql                       extensions
│   └── prometheus.yml
│
├── tests/
│   ├── unit/  integration/
│   ├── isolation/                              ← tenant leak suite (§28, §48)
│   └── fixtures/
│
├── data/                            gitignored — crawls, reports, lighthouse
├── logs/                            gitignored
└── backups/                         gitignored
```

**The structural decision worth defending:** `packages/` holds every piece of domain logic,
and both `apps/api` and `apps/worker` import from it. A crawl triggered by an endpoint and a
crawl triggered by a scheduled job execute literally the same function. Without this split,
the two paths drift and the worker's version quietly becomes the real one.

---

## §36. Tech Stack Recommendation

| Layer | Choice | Version | Cost |
|---|---|---|---|
| Frontend | Next.js (App Router) | 15.x | $0 |
| UI | React 19 + TypeScript 5.6 | | $0 |
| Styling | Tailwind CSS | 4.x | $0 |
| Components | shadcn/ui (Radix) | | $0 |
| Charts | Recharts | 2.x | $0 |
| Tables | TanStack Table | 8.x | $0 |
| API | FastAPI | 0.115+ | $0 |
| Language | Python | 3.12 | $0 |
| Package manager | uv | | $0 |
| Validation | Pydantic | 2.x | $0 |
| DB driver | asyncpg | | $0 |
| ORM / query | SQLAlchemy 2.0 Core | | $0 |
| Migrations | Alembic | | $0 |
| Database | Postgres | 16 | $0 |
| Vectors | pgvector | 0.7+ | $0 |
| Queue | Postgres `SKIP LOCKED` | | $0 |
| LLM runtime | Ollama | | $0 |
| LLM | Qwen 3.5 9B | Q4_K_M | $0 |
| Embeddings | nomic-embed-text | 768d | $0 |
| Reranker | bge-reranker-base | | $0 |
| Agents | LangGraph | | $0 |
| Clustering | HDBSCAN + UMAP | | $0 |
| HTTP client | httpx | | $0 |
| HTML parsing | selectolax | | $0 |
| Perf audit | Lighthouse CLI | | $0 |
| Logging | structlog | | $0 |
| Metrics (optional) | Prometheus + Grafana | | $0 |
| Testing | pytest, Vitest, Playwright | | $0 |
| Lint/format | Ruff, ESLint, Prettier | | $0 |
| CI | GitHub Actions | free tier | $0 |
| Static hosting | Cloudflare Pages | free tier | $0 |
| Containers | Docker Compose | | $0 |
| **Total** | | | **$0/month** |

---

## §37. Why each technology was selected

### Next.js 15 (App Router)

**Alternatives:** Remix, SvelteKit, plain Vite + React.

React Server Components are the deciding feature. The site dashboard (§11) renders eight
widgets from materialised views; with RSC each is a direct Postgres query at render time with
no client-side fetch waterfall and no API round trip. Remix is comparable but has a smaller
component ecosystem; SvelteKit is excellent but shadcn/ui and TanStack Table are React-first,
and rebuilding those is weeks of work for no user-visible gain.

### FastAPI + Python 3.12

**Alternatives:** NestJS, Django, Flask.

Python is chosen for the *worker*, and the API follows so both can share `packages/`. The
crawler needs `httpx` + `selectolax`, clustering needs `hdbscan` + `umap-learn`, and the
Ollama client is Python-first. None have equal-quality TypeScript equivalents. FastAPI over
Django because there's no need for the admin or the ORM, and its Pydantic-derived OpenAPI spec
generates the frontend's types for free. Django REST Framework would drag in a synchronous
worldview that fits a crawler badly.

### Postgres 16 + pgvector

Defended at length in §13 and §21. In short: MVCC means a 40-minute crawl never blocks the
dashboard; declarative partitioning handles the 33M-row time-series table; and keeping vectors
in the same database turns "similar pages that also rank" into one query instead of three.

### Postgres as the queue

Defended in §25. The decisive property is transactional enqueue — a job cannot reference data
whose transaction rolled back. Redis + Celery is the industry default and would be the right
call at 10,000 jobs/minute; at ~200 jobs/day it is a second service, a second persistence
model, and a new class of bug, purchased for nothing.

### Ollama + Qwen 3.5 9B

**Alternatives:** llama.cpp directly, MLX, LM Studio.

Ollama wins on three specifics rather than general convenience:

1. **The `format` parameter** — schema-constrained decoding, which §17 and §29 both depend on.
   llama.cpp offers GBNF grammars but they're far more work to generate from JSON Schema.
2. **Model lifecycle management** — `keep_alive`, automatic loading, a stable HTTP API. Doing
   this by hand around llama.cpp is real work.
3. **Already proven on this machine** — `Growleads L.S` runs Qwen through Ollama on this exact
   hardware, including the `think=False` finding that shapes §17.

MLX would likely be marginally faster on Apple silicon but has no equivalent structured-output
guarantee, which matters more here than tokens per second.

**Qwen 3.5 9B specifically:** the reasoning-model architecture with reasoning *disabled* turns
out to be an unusually good fit for schema-constrained extraction, and 9B is the largest size
that leaves adequate headroom for Postgres and the crawler on 16 GB.

### nomic-embed-text

Defended in §20. The 8,192-token context window is the decider — it embeds a full page section
without a second chunking pass, and 768 dimensions keep the index at ~700 MB rather than the
~950 MB a 1024-dim model would need.

### LangGraph

**Alternatives:** CrewAI, AutoGen, hand-rolled.

Used in deterministic mode — we author the graph; the model fills nodes and never routes.
CrewAI and AutoGen both assume chatty agent-to-agent conversation, which costs 10+ seconds per
turn on a 9B local model and is exactly the wrong shape. Hand-rolling would mean reinventing
checkpointing and step tracing, which map cleanly onto `agent_steps`.

### httpx + selectolax

**Alternatives:** Scrapy, Playwright, BeautifulSoup.

`selectolax` is a Rust-backed HTML parser roughly 5–10× faster than BeautifulSoup — meaningful
across 1,800 pages. `httpx` gives async + HTTP/2 without Scrapy's framework and its own
scheduler, which would duplicate the job queue we already have. Playwright is reserved for the
minority of JS-rendered sites and is invoked selectively, not by default — a headless Chromium
per page is ~300 MB and 20× slower.

### Lighthouse CLI, not the PageSpeed API

The PageSpeed Insights API is free but capped at ~25,000 requests/day and returns a lab result
from Google's servers. The CLI runs locally with **no quota at all**, so nightly audits of
every page of every client site are possible. It also removes one external dependency from the
critical path.

### uv

**Alternatives:** pip, Poetry, PDM.

10–100× faster than pip on cold installs, which is directly felt in `setup.sh` — the difference
between a 45-second and a 4-second dependency step. Native workspace support matches the
`packages/` + `apps/` layout. Lockfile is deterministic.

### Tailwind + shadcn/ui

shadcn is **copied into the repo, not installed as a dependency** — the components become
project code that can be edited freely. For a tool with unusual density requirements (§12),
being able to modify a table component directly rather than fighting a library's API is worth
a great deal. Radix underneath means keyboard navigation and ARIA are correct by default.

### What was deliberately rejected

| Rejected | Why |
|---|---|
| Redis | A second service for a queue Postgres already handles (§25) |
| Celery | Follows from rejecting Redis |
| Pinecone / Weaviate Cloud | Recurring cost — disqualified by §38 |
| Sentry | Recurring cost past the free tier; local error log is sufficient (§31) |
| Vercel | Recurring cost, and RSC needs a direct Postgres connection |
| Prisma | Weak support for pgvector, partitioning, and raw SQL — all of which this needs |
| Scrapy | Its scheduler duplicates the job queue |
| An ORM for reads | Analytical queries here are hand-written SQL; an ORM obscures them |
| JWTs for sessions | Cannot revoke; no benefit when auth and API share a machine (§16) |
| Microservices | One machine, one team, one deployable |

---

[← 09 Security & Ops](09-security-ops.md) · [Index](../README.md) · [Next: 11 — Costs →](11-costs.md)
