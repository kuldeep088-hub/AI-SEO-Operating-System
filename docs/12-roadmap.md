# 12 — Roadmap, Testing & Production

Sections §45–§49. [← Back to index](../README.md)

---

## §45. Development Roadmap

### Sequencing rule

**Ship in the order that produces a client-visible deliverable soonest.** Every phase ends with
something Anuj could hand to a real client. A half-built platform that generates one real
monthly report beats a fully-built platform that generates none.

### Six phases, ~24 weeks part-time

```
Phase 0  Foundation           2 weeks   ── nothing visible, everything depends on it
Phase 1  Data + Reports       8 weeks   ── ★ first real client report
Phase 2  Technical SEO        4 weeks   ── ★ first audit delivered
Phase 3  Research + Content   6 weeks   ── ★ first AI-generated content calendar
Phase 4  Content Production   4 weeks   ── ★ first published post
Phase 5  Polish + Portal      2 weeks   ── ★ client-facing dashboard live
```

Estimates assume **part-time solo development with Claude Code** (~15–20 focused hours/week).
Full-time, halve them. Two developers, roughly ×0.6 — not ×0.5, because the foundation phases
don't parallelise.

---

### Phase 0 — Foundation (2 weeks)

*Nothing user-visible. Everything else depends on getting this right.*

| Deliverable | Detail |
|---|---|
| Repo + monorepo layout | §35 exactly |
| `setup.sh` / `run.sh` | Working on a clean machine — test on a second Mac if possible |
| Docker Compose + Postgres | §34 config, digest-pinned |
| Alembic migrations | Full schema from §13, in one initial migration |
| RLS policies | Every tenant table, plus the isolation test suite |
| Auth | Google OAuth, sessions, RBAC (§16) |
| Logging, config, error classes | §30 |
| CI | All four jobs green (§33) |

**Exit criteria:** a fresh clone runs `./setup.sh && ./run.sh`, you sign in with Google, and
the tenant-isolation suite passes.

**Why RLS in Phase 0, not later:** retrofitting row-level security onto an existing schema
means auditing every query written in the interim. Two days now, two weeks later.

---

### Phase 1 — Data + Reports (8 weeks) ★

*The phase that justifies the build.*

| Week | Focus |
|---|---|
| 1–2 | GSC integration: OAuth grant, property picker, backfill, incremental sync, `gsc_daily` |
| 3 | GA4 integration: same shape, plus the GSC⋈GA4 join |
| 4 | Job queue + worker (§25), scheduler, progress SSE |
| 5 | Cross-client dashboard + site dashboard, materialised views |
| 6 | Search Console analytics screen, query/page explorer, opportunity scoring |
| 7 | Ollama runtime, prompt versioning, Report Narrator agent |
| 8 | Monthly report: data assembly, narrative, PDF, white-labelling |

**Exit criteria:** connect a real client's GSC and GA4, wait for a nightly sync, generate a
monthly report Anuj would actually send. **This is the moment the project becomes worth
continuing** — and the moment to honestly assess whether the local model's narrative quality
is good enough. If it isn't, that finding arrives in week 8, not week 20.

**Risk:** GSC's 16-month backfill is slow and quota-sensitive. Build it resumable from day
one — a backfill that fails at month 12 and restarts from zero is a very bad week.

---

### Phase 2 — Technical SEO (4 weeks) ★

| Week | Focus |
|---|---|
| 9 | Crawler core: async fetch, robots.txt, SSRF guard (§29), JSONL output |
| 10 | Parser + rules engine: ~30 rules producing `issues` |
| 11 | Crawl diffing, "new this week", Technical Auditor agent |
| 12 | Lighthouse CLI integration, health scoring, broken links, on-page checker |

**Exit criteria:** a full crawl of a real 1,800-page client site completing in under 25
minutes, with a diff against the previous crawl and AI-written remediation.

**Risk:** the crawler is the most bug-prone component in the system — encodings, redirect
loops, malformed HTML, JS-rendered sites, WAFs. Budget the full week 9 for edge cases and test
against real client sites, not a toy fixture.

---

### Phase 3 — Research + Content Planning (6 weeks) ★

| Week | Focus |
|---|---|
| 13 | Embedding pipeline, pgvector, `content_hash` short-circuit |
| 14 | Keyword clustering: UMAP + HDBSCAN + cluster labelling |
| 15 | Topic clusters, coverage mapping against existing content |
| 16 | Content planner, calendar, opportunity ranking |
| 17 | Internal linking: link graph, PageRank, similarity suggestions |
| 18 | RAG retrieval layer + AI Chat Assistant with citations |

**Exit criteria:** a content calendar generated from real GSC data, with briefs, that Priya
would work from.

**Risk:** cluster quality. Bad clusters make every downstream module wrong. Build the eval set
(§18) *before* tuning, not after — otherwise tuning is guesswork.

---

### Phase 4 — Content Production (4 weeks) ★

| Week | Focus |
|---|---|
| 19 | Brief builder: research, entities, outline generation, approval flow |
| 20 | Blog generator: section-by-section pipeline (§17) |
| 21 | Draft editor, live coverage scoring, Editor agent |
| 22 | Schema generator, WordPress publishing, performance loop-back |

**Exit criteria:** a post that went brief → outline → draft → edit → WordPress without leaving
the tool, published on a real client site.

**Risk: this is the phase most likely to disappoint**, and the plan says so up front (§5.9).
Measure editing time honestly in week 21. If a draft takes longer to fix than to write, ship
the brief builder — which is genuinely valuable on its own — and mark the generator
experimental rather than pretending.

---

### Phase 5 — Polish + Client Portal (2 weeks) ★

| Week | Focus |
|---|---|
| 23 | Client portal, portal tokens, white-labelling, sharing |
| 24 | Notifications, action plan generator, weekly reports, settings polish |

**Exit criteria:** a client opens a live dashboard link and sees only their own data.

---

### Deferred, deliberately

| Item | Condition to revisit |
|---|---|
| AI Overview optimisation | When SERP data becomes reliable — i.e. if Apify is enabled |
| Competitor analysis (crawl-based) | Phase 6, once core work is stable |
| Backlink tracker | Phase 6; GSC-only version is a two-day job |
| Google Business Profile | When a client actually needs local SEO |
| Free tools site | Independent of the main app; can be built any weekend |
| Billing | Only if hosted (§51) |

---

## §46. Sprint Planning

Two-week sprints, twelve total. Each has one demoable outcome — if it can't be demoed, the
sprint was scoped wrong.

| # | Weeks | Goal | Demo |
|---|---|---|---|
| 1 | 1–2 | Foundation | Clean clone → setup → login. Isolation suite green. |
| 2 | 3–4 | GSC pipeline | Real client's 16-month history in Postgres |
| 3 | 5–6 | GA4 + jobs | Nightly sync runs unattended; progress visible live |
| 4 | 7–8 | Dashboards | Site dashboard <300 ms against real data |
| 5 | 9–10 | AI + reports | **Monthly report for a real client** |
| 6 | 11–12 | Crawler | 1,800-page crawl with issue list |
| 7 | 13–14 | Diffing + audit | "14 new 404s this week" with AI remediation |
| 8 | 15–16 | Embeddings + clusters | 3,400 queries → ~47 labelled clusters |
| 9 | 17–18 | Planner + linking | Content calendar + 31 link suggestions |
| 10 | 19–20 | RAG + chat | "Why did traffic drop?" answered with citations |
| 11 | 21–22 | Content pipeline | **Post published to WordPress** |
| 12 | 23–24 | Portal + polish | Client opens their own live dashboard |

### Sprint mechanics

**Definition of ready.** A story enters a sprint only with: acceptance criteria, the doc
section it implements, its test approach, and — for AI work — its eval cases.

**Definition of done.**
- Tests pass, including the isolation suite
- Type checks clean (mypy strict on `packages/`, `tsc --noEmit`)
- Works against **real client data**, not fixtures
- Docs updated if behaviour diverged from this spec
- No new dependency without a one-line justification

**The last one matters most:** every feature must be verified against a real client site.
Synthetic fixtures hide encoding bugs, WAFs, weird redirects, and GSC's quirks — all of which
appear on day one in production and never in tests.

### Velocity assumptions

| Factor | Effect |
|---|---|
| Solo + Claude Code | Baseline |
| Familiar stack (Next.js, Python, Postgres) | +20% |
| Novel: local LLM pipeline, crawler at scale | −30% on Phases 3–4 |
| Real client data available from week 3 | +15% — bugs surface early |

Phases 3 and 4 carry the uncertainty; Phases 0–2 are conventional engineering.

---

## §47. GitHub Milestones

Twelve milestones, one per sprint. Issue labels:

```
type:     feature · bug · chore · docs · spike
area:     db · api · web · worker · crawler · ai · integrations · infra
priority: p0-blocker · p1-must · p2-should · p3-nice
size:     xs(<2h) · s(<1d) · m(<3d) · l(<1w) · xl(split it)
```

`size: xl` is a signal, not a label — anything that big should be split before work starts.

### Milestone 1 — Foundation

```
p0  Monorepo scaffold, uv workspace, Next.js app                    [chore/infra]  m
p0  docker-compose: Postgres 16 + pgvector, tuned                   [chore/infra]  s
p0  Alembic initial migration — full §13 schema                     [feature/db]   l
p0  RLS policies on every tenant table                              [feature/db]   m
p0  Tenant-isolation test suite                                     [feature/db]   m
p0  Google OAuth: identity grant, sessions, RBAC                    [feature/api]  l
p1  setup.sh + run.sh, idempotent, tested on a clean machine        [chore/infra]  m
p1  structlog with redaction processor                              [feature/api]  s
p1  CI: four jobs green                                             [chore/infra]  m
```

### Milestone 5 — AI + Reports (the pivotal one)

```
p0  Ollama runtime wrapper: schema enforcement, think=False default [feature/ai]   m
p0  prompt_versions seeding + version selection                     [feature/ai]   s
p0  Report Narrator agent + LangGraph graph                         [feature/ai]   l
p0  Monthly report data assembly (frozen snapshot)                  [feature/api]  m
p0  Report review + edit UI                                         [feature/web]  m
p1  PDF generation, white-labelled                                  [feature/web]  m
p1  Eval set: 20 real months with human summaries                   [feature/ai]   m
p2  Weekly report (diff-based)                                      [feature/api]  s
```

### Milestone 11 — Content Pipeline (the risky one)

```
p0  Brief builder: research → entities → outline                    [feature/ai]   xl → split
p0  Writer agent: section-by-section generation                     [feature/ai]   l
p0  Editor agent: voice + flow pass                                 [feature/ai]   m
p0  Draft editor UI with live coverage scoring                      [feature/web]  l
p1  Schema generator (constrained JSON-LD)                          [feature/ai]   m
p1  WordPress publishing via Application Password                   [feature/int]  m
p1  SPIKE: measure editing time on 5 real drafts                    [spike/ai]     m
p2  Performance loop-back (post → GSC after 30 days)                [feature/api]  s
```

**The spike is the important issue in this milestone.** It is a decision gate, not a task: if
editing a generated draft takes longer than writing from the brief, the generator ships as
experimental and the brief builder becomes the headline feature.

---

## §48. Testing Strategy

### The pyramid, adjusted for what actually breaks here

```
        ╱╲          E2E (Playwright)  ~15 tests
       ╱  ╲         critical journeys only
      ╱────╲
     ╱      ╲       Integration       ~120 tests
    ╱        ╲      real Postgres, real HTTP fixtures
   ╱──────────╲
  ╱            ╲    Unit              ~400 tests
 ╱______________╲   rules, scoring, parsing, chunking

  ┌──────────────┐
  │  Isolation   │  ~50 tests — runs as its own CI job
  └──────────────┘
  ┌──────────────┐
  │  AI evals    │  ~90 cases — runs on prompt changes
  └──────────────┘
```

The two boxes below the pyramid are what make this project's testing unusual, and they're the
ones worth building first.

### Tenant isolation — the highest-value suite

```python
# tests/isolation/test_cross_tenant.py
@pytest.mark.parametrize("route", ALL_ROUTES)
async def test_no_cross_tenant_read(route, org_a, org_b, client):
    """Every route, with org_a's principal, must never return org_b's data."""
    resp = await client.request(route.method, route.path_for(org_b),
                                headers=principal_headers(org_a))
    assert resp.status_code in (403, 404) or resp.json()["data"] == []


@pytest.mark.parametrize("table", TENANT_TABLES)
async def test_rls_blocks_raw_sql(table, db, org_a, org_b):
    """Even a raw query with no WHERE clause must not cross tenants."""
    async with db.transaction() as tx:
        await tx.execute("SELECT set_config('app.current_org_id', $1, true)", org_a.id)
        rows = await tx.fetch(f"SELECT * FROM {table}")     # deliberately unfiltered
        assert all(r["org_id"] == org_a.id for r in rows)


async def test_client_viewer_scope(db, portal_token_for_client_a, client_b_site):
    """A portal token must not reach a sibling client in the same org."""
    resp = await client.get(f"/v1/orgs/{org.id}/sites/{client_b_site.id}",
                            headers=portal_headers(portal_token_for_client_a))
    assert resp.status_code == 403
```

`ALL_ROUTES` is generated from the FastAPI app, so **a new endpoint is automatically covered**.
Forgetting to add a test is not possible; forgetting to add the scoping is caught immediately.

### AI evals

Small models regress silently when prompts change (§18). Without an eval set, prompt tuning is
superstition.

```
packages/agents/evals/
├─ technical_auditor/cases.jsonl      40 real findings + human-written expected output
├─ content_strategist/cases.jsonl     30 clusters + human labels and intents
├─ report_narrator/cases.jsonl        20 real months + human summaries
└─ rubrics.py
```

| Check | Method | Gate |
|---|---|---|
| Schema validity | Structural | **100%** — any failure blocks |
| Field accuracy | Exact match vs human label | ≥85% |
| No unevidenced causal claims | Checker pass | **100%** — the highest-value check |
| Numeric fidelity | Every number in output appears in input | **100%** |
| Style | Human spot-check, 10% sample | subjective |

A prompt version cannot be marked `is_active` until it scores at least as well as the current
active version. Enforced in CI (§33).

**"No unevidenced causal claims" is the one that protects the product.** A report saying
"traffic dropped because of a Google update" when the data shows only a correlation is worse
than no report — it gets repeated to a client and is wrong.

### Integration tests

Against a **real Postgres** (Docker), never SQLite or a mock. RLS, partitioning, `SKIP LOCKED`,
and pgvector cannot be faked.

```python
async def test_job_queue_no_double_dequeue(db):
    """Two workers must never claim the same job."""
    await enqueue("crawl_site", site_id=site.id)
    results = await asyncio.gather(dequeue("crawl"), dequeue("crawl"))
    assert len([r for r in results if r is not None]) == 1


async def test_expired_lease_reclaimed(db):
    job = await enqueue("crawl_site", site_id=site.id)
    await dequeue("crawl")
    await db.execute("UPDATE jobs SET lease_expires_at = now() - interval '1 min'")
    await reclaim_expired()
    assert (await get_job(job.id)).status == "queued"
```

External APIs are recorded fixtures (VCR-style), not live calls — CI must not depend on
Google's uptime or consume real quota.

### Crawler tests

The most bug-prone component (§45), so it gets a deliberately hostile fixture set:

| Fixture | Asserts |
|---|---|
| Redirect chain, 5 hops | Followed to the cap, then stopped |
| Redirect loop | Detected, not infinite |
| Malformed HTML, unclosed tags | Parsed without crashing |
| Non-UTF-8 (Shift-JIS, Latin-1) | Encoding detected correctly |
| 10 MB page | Truncated at the cap |
| `robots.txt` disallow | Path skipped |
| `Crawl-delay: 10` | Honoured over our default |
| **`http://internal.local` → 127.0.0.1** | **SSRF blocked** |
| **Public URL 302 → 169.254.169.254** | **SSRF blocked on the redirect hop** |

The two SSRF cases are non-negotiable — they are the difference between a crawler and an
attack tool (§29).

### E2E — critical journeys only

Playwright, ~15 tests, mapped to §7:

1. First run → onboarding → connect Google (mocked OAuth) → first data
2. Dashboard → drill into an issue → view remediation
3. Chat: ask a question, receive an answer with citations
4. Brief → outline → approve → draft → editor
5. Generate report → edit narrative → approve → PDF
6. Create portal token → open in a clean context → verify scoping
7. Add client → configure → first crawl

E2E is deliberately small. It is slow and brittle; integration tests catch more per minute.

### Coverage targets

| Area | Target | Why |
|---|---|---|
| `packages/analysis` | 90% | Pure logic, cheap to test, wrong answers are silent |
| `packages/crawler` | 85% | Bug-prone |
| `packages/db` | 80% | |
| `apps/api` | 75% | |
| `apps/worker` | 70% | |
| `apps/web` | 50% | E2E covers the paths that matter |
| **Isolation suite** | **100% of routes** | Non-negotiable |

CI fails below 70% overall — a floor, not a goal. Chasing 95% on `apps/web` would be theatre.

---

## §49. Production Checklist

"Production" means: real client data, results sent to real clients.

### Before the first real client

**Data & correctness**
- [ ] GSC backfill completes for a 16-month history without manual intervention
- [ ] GSC numbers reconciled against the Search Console UI for three sites, three date ranges
- [ ] GA4 numbers reconciled against the GA4 UI
- [ ] Timezone handling verified — GSC reports in PT, GA4 in property timezone, we store UTC
- [ ] The GSC⋈GA4 landing-page join verified on a site with query-string URLs
- [ ] Crawl of a real 1,800-page site matches Screaming Frog's page count within 2%

**Security**
- [ ] Tenant-isolation suite green, covering every route
- [ ] Portal token scoped to one client, verified in a clean browser profile
- [ ] OAuth tokens confirmed encrypted in the database (inspect the raw bytes)
- [ ] SSRF guard tested against private ranges *and* redirect-based bypass
- [ ] Postgres bound to `127.0.0.1` — verified with `lsof -i :5432`
- [ ] `.env` in `.gitignore`, no secrets in git history (`git log -S` for key patterns)
- [ ] FileVault on
- [ ] Backup restored to a scratch database successfully — **an untested backup is not a backup**

**Reliability**
- [ ] Nightly schedule runs unattended for seven consecutive days
- [ ] Laptop closed mid-crawl → job reclaimed by lease, completes next run
- [ ] Ollama killed mid-inference → job retries, other queues unaffected
- [ ] Revoked OAuth token → that client pauses, others keep syncing
- [ ] Disk at 85% → prune job runs, warning raised
- [ ] Dead-lettered job surfaces in notifications with a useful error

**AI quality**
- [ ] Eval suites pass at or above baseline for all three agents
- [ ] Ten report narratives reviewed by a human — zero unevidenced causal claims
- [ ] Chat citations verified: every bracketed reference resolves to a real row
- [ ] Brand voice memory demonstrably changes output between two clients

**Performance**
- [ ] Site dashboard p95 < 300 ms against real data volume
- [ ] Chat first token < 3 s
- [ ] Nightly window fits with 30% headroom at current client count

**Operations**
- [ ] `./backup.sh` scheduled or habitual, with a restore actually rehearsed
- [ ] Weekly `system_health` notification arriving and being read
- [ ] Log rotation confirmed (fill a log, watch it rotate)
- [ ] Recovery documented: what to do if Postgres won't start, Ollama won't load, disk is full

### Before sending a report to a client

- [ ] Every number in the report traced to its source table
- [ ] Narrative read end-to-end by a human, causal claims checked
- [ ] White-labelling correct: agency logo, client name, no tool branding anywhere
- [ ] PDF renders correctly on mobile and desktop
- [ ] Date ranges match what the client expects (calendar month, not trailing 30 days)
- [ ] No other client's data anywhere in the document

### Ongoing

| Cadence | Task |
|---|---|
| Weekly | Read the `system_health` notification; clear dead-lettered jobs |
| Weekly | `./backup.sh` |
| Monthly | Review AI eval scores for drift |
| Monthly | Check disk headroom and prune |
| Quarterly | Restore a backup to a scratch DB |
| Quarterly | `pip-audit` / `npm audit`, update dependencies |
| Quarterly | Re-verify Google API quotas against current docs (§38) |

### The one that gets skipped

**Rehearse the restore.** Every checklist has it; almost nobody does it. This system holds
fifteen clients' historical data and the encryption key for their OAuth connections. Losing it
means re-authorising every client and permanently losing history that Search Console will only
give back for 16 months.

Do the restore. Once, properly, before the first client depends on this.

---

[← 11 Costs](11-costs.md) · [Index](../README.md) · [Next: 13 — Business →](13-business.md)
