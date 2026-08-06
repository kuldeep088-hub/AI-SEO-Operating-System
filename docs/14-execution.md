# 14 — Execution

Sections §58–§60. [← Back to index](../README.md)

---

## §58. Complete Development Timeline

### 24 weeks, part-time, solo with Claude Code

| Week | Sprint | Focus | Milestone |
|---|---|---|---|
| 1 | 1 | Monorepo, Docker, Postgres, migrations | |
| 2 | 1 | RLS, isolation suite, OAuth, sessions, CI | **Foundation done** |
| 3 | 2 | GSC OAuth grant, property picker, API client | |
| 4 | 2 | GSC backfill + incremental sync, `gsc_daily` | **Real data landed** |
| 5 | 3 | GA4 integration, the GSC⋈GA4 join | |
| 6 | 3 | Job queue, worker pool, scheduler, progress SSE | **Runs unattended** |
| 7 | 4 | Materialised views, site dashboard | |
| 8 | 4 | Cross-client dashboard, GSC analytics screen | **Dashboards live** |
| 9 | 5 | Ollama runtime, prompts, schema enforcement | |
| 10 | 5 | Report Narrator, monthly report, PDF | **★ FIRST CLIENT REPORT** |
| 11 | 6 | Crawler core, robots, SSRF guard | |
| 12 | 6 | Parser, ~30 rules, `issues` | **Crawl works** |
| 13 | 7 | Crawl diffing, "new this week" | |
| 14 | 7 | Technical Auditor, Lighthouse, health score | **★ FIRST AUDIT** |
| 15 | 8 | Embedding pipeline, pgvector, `content_hash` | |
| 16 | 8 | UMAP + HDBSCAN clustering, cluster labelling | **Clusters work** |
| 17 | 9 | Topic clusters, coverage mapping, content planner | |
| 18 | 9 | Internal linking, link graph, suggestions | **★ CONTENT CALENDAR** |
| 19 | 10 | RAG retrieval, hybrid search, reranking | |
| 20 | 10 | Chat Assistant with citations | **Chat works** |
| 21 | 11 | Brief builder, outline approval | |
| 22 | 11 | Writer + Editor agents, draft editor, WordPress | **★ FIRST POST PUBLISHED** |
| 23 | 12 | Client portal, tokens, white-labelling | |
| 24 | 12 | Notifications, action plan, settings, polish | **★ PORTAL LIVE** |

### Milestones by calendar

Starting **6 August 2026** at ~15–20 focused hours/week:

| Date | Milestone |
|---|---|
| ~20 Aug 2026 | Foundation complete |
| ~17 Sep 2026 | Real GSC + GA4 data flowing |
| **~15 Oct 2026** | **First real client monthly report** |
| ~12 Nov 2026 | Technical scanner + audits |
| ~10 Dec 2026 | Keyword clustering + content planner |
| ~7 Jan 2027 | AI chat over client data |
| **~4 Feb 2027** | **First AI-assisted post published** |
| ~18 Feb 2027 | Client portals live |

### The date that matters

**~15 October 2026 — the first real client report.** That is the go/no-go. If reporting works
and saves genuine hours, everything after is upside. If it doesn't, stop at week 10 having
learned something for ten weeks of work rather than twenty-four.

Every phase after Phase 1 is independently useful (§56, risk 4). Stopping at any milestone
leaves working software, not a half-finished system.

### Compression options

| Approach | New timeline | Trade-off |
|---|---|---|
| Full-time | ~12 weeks | Agency work stops |
| Phase 1 only, then reassess | 10 weeks | Reporting only — still worth it |
| Skip Phase 4 (content) | 20 weeks | The riskiest phase removed |
| Two developers | ~15 weeks | Phases 0–2 don't parallelise well |

**The most sensible compression is "Phase 1 only, then reassess."** Ten weeks for automated
monthly reporting across fifteen clients is a defensible investment on its own.

---

## §59. Claude Code Implementation Strategy

### The core idea

This documentation *is* the specification Claude Code implements against. The strategy is to
make that specification reachable, enforce the architecture automatically, and keep each unit
of work small enough to verify.

### `CLAUDE.md` — the file that shapes every session

Place at repo root. This is the highest-leverage file in the project.

```markdown
# AI SEO Operating System

Local-first SEO platform for Growleads Agency. **$0/month recurring cost is a hard
constraint, not a preference.**

## Before you write code

Read the relevant `docs/` section first. The docs are the spec:

| Working on | Read |
|---|---|
| Schema, queries, migrations | `docs/05-database.md` |
| Endpoints, auth, RBAC | `docs/06-api-auth.md` |
| Agents, prompts, RAG, embeddings | `docs/07-ai-architecture.md` |
| Jobs, queue, crawler limits, tenancy | `docs/08-infrastructure.md` |
| Security, logging, monitoring | `docs/09-security-ops.md` |
| Stack decisions and rationale | `docs/10-deployment.md` §36–37 |
| UI layout and screens | `docs/04-ui-ux.md` |

## Hard rules — violating these is a bug, not a style preference

1. **No paid service in a default code path.** Paid services exist only behind
   `SerpProvider` / `LLMProvider` adapters, off by default. If you're about to add a
   dependency with a subscription, stop.
2. **`org_id` on every tenant table, RLS policy on every tenant table.** No exceptions.
3. **Prompts live in `prompt_versions`, never in Python string literals.**
4. **`think=False` for structured AI calls.** Reasoning on is ~30× slower and buys nothing
   when output is schema-constrained. Only Report Narrator, Chat, and Action Plan set it on.
5. **Never let the model compute a number.** Compute in SQL, pass it in, ask the model to
   explain it.
6. **Never state a cause without evidence.** Reports and chat say "X happened, and Y occurred
   on the same date," not "X happened because of Y."
7. **Domain logic goes in `packages/`.** `apps/api` and `apps/worker` both import it. Never
   duplicate logic between them.
8. **Every external fetch goes through `packages/crawler/ssrf.py`.** No bare `httpx.get` on a
   user- or content-supplied URL.
9. **Secrets never logged.** Redaction is a structlog processor — don't bypass it.
10. **New dependency requires a one-line justification** in the PR description.

## Commands

    ./setup.sh              install / update everything (idempotent)
    ./run.sh                start everything, Ctrl-C stops all
    ./run.sh --prod         production mode
    uv run pytest           Python tests
    uv run pytest tests/isolation   ← run before every commit touching data access
    uv run alembic revision --autogenerate -m "..."
    cd apps/web && npm run dev

## Conventions

- Python: Ruff (line 100), mypy strict on `packages/`, async everywhere
- SQL: hand-written for analytics; SQLAlchemy Core for CRUD; never an ORM for reporting queries
- TypeScript: strict, no `any`, types generated from OpenAPI into `lib/types.gen.ts`
- Tests: real Postgres, never SQLite or mocks for DB behaviour
- Commits: conventional commits, reference the doc section implemented
```

### Working sequence per feature

The pattern that works, and the order matters:

```
1. Plan mode      "Read docs/05-database.md §13.4 and docs/08-infrastructure.md §24.
                   Plan the GSC sync job." → review the plan before any code
2. Schema first   migration + model + repository, with tests
3. Domain logic   in packages/, pure, unit-tested
4. Wire it        API route and/or job handler — thin, no logic here
5. UI last        the screen from docs/04-ui-ux.md
6. Real data      run it against an actual client property before calling it done
```

**Step 6 is the one that gets skipped and shouldn't.** Fixtures hide encoding bugs, WAFs,
weird redirects, and GSC's own quirks — all of which appear immediately in production.

### Prompt recipes that work on this codebase

**Starting a phase:**

> Read `docs/12-roadmap.md` §45 Phase 2 and `docs/08-infrastructure.md` §27. Plan the crawler
> core: async fetch, robots.txt, SSRF guard, JSONL output. Follow the crawler section of
> `docs/35` for file placement. Don't write code yet — show me the plan.

**Implementing against a spec section:**

> Implement the `jobs` table dequeue and lease logic exactly as specified in
> `docs/08-infrastructure.md` §25. Include the reclaim sweep and the retry classification.
> Write the integration tests from `docs/12-roadmap.md` §48 first.

**When something diverges from the doc:**

> The GSC API returns `position` as 1-indexed but our opportunity formula assumes otherwise.
> Fix the code and update `docs/11-costs.md` §43 in the same commit so the spec stays true.

**AI work specifically:**

> Add the Technical Auditor agent. Prompt goes in `packages/agents/prompts/` and is seeded
> into `prompt_versions` — not a string literal. Output schema in `schemas.py`. `think=False`.
> Add 5 eval cases to `evals/technical_auditor/cases.jsonl` from real crawl findings.

### Subagent split for parallel work

Where work genuinely parallelises, split by *layer*, not by feature — layers have clean
interfaces; features cut across everything:

| Agent | Scope | Reads |
|---|---|---|
| Schema | migrations, models, repositories | §13 |
| API | routers, deps, middleware | §15–16 |
| Worker | job handlers, scheduler | §24–25 |
| AI | agents, prompts, evals | §17–22 |
| Web | screens, components | §8–12 |

Run at most two concurrently, and never two that touch the same layer. Schema changes should
be serialised — two agents writing migrations produces conflicts that are tedious to unpick.

### What to hand-check rather than trust

| Area | Why |
|---|---|
| RLS policies | A subtly wrong policy passes tests and leaks data |
| SSRF guard | Bypasses are non-obvious; check the redirect path specifically |
| Opportunity / health formulas | Plausible-looking wrong maths is invisible |
| GSC and GA4 date handling | Timezones, GSC's 3-day lag, and off-by-one date ranges |
| Report narratives | Read ten of them before sending any to a client |
| Anything touching `.env` | One committed key means rotating everything |

### The pitfall to watch for

The most likely failure mode is **plausible code that doesn't match the spec** — a queue
implementation without the lease sweep, an RLS policy missing the `client_viewer` branch, a
crawler without conditional requests. Each looks correct, passes a basic test, and quietly
loses a property this document depends on.

The defence is the same in every case: cite the doc section in the prompt, and verify the
specific property the section calls out — not just that the feature works.

---

## §60. Final Development Checklist

### Before writing any code

**Accounts and access**
- [ ] Google Cloud project created
- [ ] Search Console API, Analytics Data API enabled
- [ ] OAuth 2.0 client created, `http://localhost:8000/v1/auth/google/callback` registered
- [ ] Consent screen configured (External, Testing mode is fine)
- [ ] Scopes added: `webmasters.readonly`, `analytics.readonly`
- [ ] **Verified: your Google account has GSC access to at least one real client site**
- [ ] Google Ads developer token requested (optional, for search volumes)
- [ ] GitHub repo created, private

**Machine**
- [ ] Postgres available — **either** Docker Desktop running, **or** nothing to do
      (`scripts/pg.py` falls back to bundled PostgreSQL 16 + pgvector; see §32)
- [ ] Node 20+, Python 3.12+
- [ ] **Ollama located.** `Ollama.app` installs to `~/Applications` and is **not on `PATH`** —
      `setup.sh` resolves it and symlinks `./bin/ollama` (§32). Verify:
      `~/Applications/Ollama.app/Contents/Resources/ollama list`
- [ ] `qwen3.5:9b` pulled (~5.5 GB) — already present on this machine
- [ ] `nomic-embed-text` pulled (~275 MB)
- [ ] Ollama server responds: `curl -s localhost:11434/api/tags`
- [ ] ≥ 30 GB free disk
- [ ] FileVault on

**Decisions confirmed**
- [ ] Which client site is the guinea pig for Phase 1
- [ ] Where backups go
- [ ] Whether the free tools site (§44) is in scope now or later

### The verification that matters most

> **Sign in to Search Console with the Google account you'll use, and confirm you can see a
> real client's data.**

Everything in this document rests on that single condition (§3). If it fails, stop and resolve
access before writing a line of code.

### Week 1 exit criteria

- [ ] Fresh clone → `./setup.sh` → `./run.sh` works on a clean machine
- [ ] Google sign-in works end to end
- [ ] Migrations apply cleanly; every tenant table has an RLS policy
- [ ] Isolation test suite passes
- [ ] CI green on all four jobs
- [ ] `CLAUDE.md` written and accurate

### Phase 1 exit criteria — the real gate

- [ ] 16 months of a real client's GSC data in Postgres
- [ ] Numbers reconciled against the Search Console UI (3 date ranges, ±1%)
- [ ] GA4 data joined to GSC on landing page, verified against the GA4 UI
- [ ] Nightly sync ran unattended for 7 consecutive days
- [ ] Site dashboard p95 < 300 ms against real data volume
- [ ] A monthly report generated, reviewed, and **sent to a real client**
- [ ] Report narrative contained zero unevidenced causal claims
- [ ] Time to produce that report measured and compared against the manual process

**That last item is the point of the whole project.** If the report took 90 minutes to review
and fix, the AI layer needs work. If it took 10, the thesis is proven and the remaining phases
are worth building.

### Before any client sees anything

- [ ] Full §49 production checklist complete
- [ ] Backup taken **and restored to a scratch database**
- [ ] Portal token tested in a clean browser profile — verified it reaches exactly one client
- [ ] White-labelling checked: no tool branding anywhere in a client deliverable
- [ ] Ten AI narratives read end to end by a human

### The three rules to keep

**1. Every phase must be independently useful.** If work stops at week 10, the agency has
automated monthly reporting. At week 14, a technical scanner too. Never build a phase whose
value depends on a later phase existing.

**2. Real client data from week 3.** Not fixtures. Every bug that matters comes from real
sites — odd encodings, WAFs, redirect chains, GSC's lag and quirks.

**3. Update the docs when the code diverges.** A specification that no longer matches the
implementation is worse than none, because it actively misleads the next session. Same PR,
every time.

### Start here

```bash
cd "/Users/kuldeep/Growleads AI SEO"
./serve-docs.sh                    # read the spec at localhost:4000

# Then, in Claude Code:
#   "Read docs/12-roadmap.md §45 Phase 0 and docs/05-database.md §13.
#    Plan the foundation sprint. Don't write code yet."
```

---

[← 13 Business](13-business.md) · [Index](../README.md)
