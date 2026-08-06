# 08 — Infrastructure

Sections §23–§28. [← Back to index](../README.md)

---

## §23. File Storage Strategy

### No object store

S3, R2, and every managed alternative carry a recurring cost or an account dependency. The
machine has a disk. Use it.

```
data/                                 # gitignored, backed up as one directory
├── crawls/
│   └── {site_id}/{crawl_id}/
│       ├── pages.jsonl.gz            # raw crawl output, one JSON per line
│       └── meta.json                 # config, timing, counts
├── lighthouse/
│   └── {site_id}/{run_id}.json.gz    # full Lighthouse report
├── reports/
│   └── {site_id}/{report_id}.pdf
├── exports/
│   └── {user_id}/{export_id}.csv     # user-triggered, short-lived
├── uploads/
│   └── {org_id}/logo.png             # agency + client branding
└── models/                           # reserved; Ollama manages its own under ~/.ollama
```

**Postgres stores paths, never blobs.** `lighthouse_runs.raw_path`, `reports.pdf_path`,
`crawls` artefacts. Large binary in Postgres bloats backups and slows every `pg_dump` for no
benefit when the file lives on the same disk.

### Why JSONL + gzip for crawl output

A crawl of 1,842 pages produces ~40 MB of raw HTML-derived data. Options considered:

| Option | Verdict |
|---|---|
| Straight into Postgres | Bloats the `pages` table with data queried once |
| Parquet | Excellent compression and columnar reads, but adds `pyarrow` (~90 MB) for one use |
| **JSONL + gzip** | Streamable line-by-line (never load 40 MB into RAM), ~85% compression, zero new dependencies |

**Recommendation: JSONL + gzip.** The streaming property is what decides it — the parser
processes one page at a time, so memory stays flat regardless of site size. On a 16 GB machine
shared with a 5.5 GB model, that matters.

### Retention

Enforced by a nightly `prune_storage` job, not by hope.

| Artefact | Retention | Reason |
|---|---|---|
| Crawl JSONL | Last 4 crawls per site | Diffing needs 2; 4 gives a month of weekly history |
| Lighthouse JSON | 90 days | Scores are in Postgres; the raw report is for debugging |
| Report PDFs | Forever | Client deliverables. Never auto-delete. |
| Exports | 7 days | Transient by nature |
| Uploads | Until replaced | Branding assets |

```python
# apps/worker/jobs/prune_storage.py
async def prune_storage():
    for site in await all_sites():
        crawls = await recent_crawls(site.id, limit=None)
        for c in crawls[4:]:
            shutil.rmtree(DATA / "crawls" / str(site.id) / str(c.id), ignore_errors=True)
    cutoff = now() - timedelta(days=90)
    for p in (DATA / "lighthouse").rglob("*.json.gz"):
        if datetime.fromtimestamp(p.stat().st_mtime, UTC) < cutoff:
            p.unlink()
    # …exports at 7 days
    await check_disk_headroom(warn_at=0.80, critical_at=0.92)
```

Disk headroom is checked on every run. At 80% a notification fires; at 92% crawl jobs refuse
to enqueue rather than filling the disk and taking Postgres down with them.

### Backup

One command, because a backup nobody runs is not a backup:

```bash
./backup.sh              # → backups/seo-os-2026-11-14.tar.zst
```

```bash
pg_dump --format=custom --compress=0 "$DATABASE_URL" > "$TMP/db.dump"
tar --use-compress-program=zstd -cf "$OUT" -C "$ROOT" data .env --directory="$TMP" db.dump
```

Roughly 1.2 GB at 15 clients, two years. `.env` is included because it holds
`TOKEN_ENCRYPTION_KEY` — without it the backup's OAuth tokens are permanently undecryptable.
That also means **the backup must be treated as a secret**, which `backup.sh` prints as a
warning on every run.

---

## §24. Background Job Architecture

### Job taxonomy

| Job | Trigger | Queue | Typical duration |
|---|---|---|---|
| `gsc_sync` | nightly + manual | `sync` | 20 s – 4 min |
| `gsc_backfill` | on site creation | `sync` | 5 – 25 min |
| `ga4_sync` | nightly + manual | `sync` | 15 s – 2 min |
| `crawl_site` | weekly + manual | `crawl` | 5 – 40 min |
| `crawl_competitor` | weekly | `crawl` | 3 – 15 min |
| `lighthouse_run` | weekly | `crawl` | 2 – 8 min |
| `diff_crawl` | after `crawl_site` | `default` | 2 – 20 s |
| `embed_pages` | after `crawl_site` | `ai` | 30 s – 6 min |
| `analyse_issues` | after `diff_crawl` | `ai` | 20 s – 3 min |
| `cluster_keywords` | after `gsc_sync`, weekly | `ai` | 1 – 3 min |
| `suggest_links` | weekly | `ai` | 1 – 4 min |
| `generate_draft` | user | `ai` | 3 – 6 min |
| `weekly_report` | weekly | `report` | 1 – 3 min |
| `monthly_report` | monthly | `report` | 2 – 5 min |
| `refresh_views` | after any sync | `default` | 2 – 15 s |
| `prune_storage` | nightly | `default` | 5 – 30 s |
| `create_partitions` | monthly | `default` | < 1 s |

### Queues and worker allocation

```
sync    → 2 workers    network-bound, Google API quota is the limit
crawl   → 4 workers    network-bound, polite per-host rate limiting
ai      → 1 worker     GPU-bound — Ollama is the bottleneck (§17)
report  → 1 worker     calls ai internally; more would just contend
default → 2 workers    fast bookkeeping
```

**The `ai` queue has exactly one worker and that is not a placeholder.** One Ollama instance,
one GPU. Two AI workers halve each request's speed with no throughput gain, and a second
resident model would exceed 16 GB. Everything AI-related serialises through this queue by
design.

### Chaining

Jobs enqueue their successors rather than a scheduler encoding the dependency graph. This
keeps the DAG next to the work:

```python
# apps/worker/jobs/crawl_site.py
async def run(job: Job):
    crawl = await crawler.run(job.site_id, config=job.payload)
    await enqueue("diff_crawl",  site_id=job.site_id, crawl_id=crawl.id, queue="default")
    await enqueue("embed_pages", site_id=job.site_id, crawl_id=crawl.id, queue="ai")
    return {"pages": crawl.pages_crawled, "failed": crawl.pages_failed}
```

A failure in `embed_pages` doesn't roll back the crawl. Each link in the chain is
independently retryable, which matters when the Ollama process is the thing that died.

### Scheduling

`schedules` (§13.8) holds cron expressions; a single-row advisory lock ensures only one
worker evaluates them:

```python
async def tick():
    async with conn.transaction():
        got = await conn.fetchval("SELECT pg_try_advisory_xact_lock(4815162342)")
        if not got:
            return                        # another worker owns this tick
        due = await conn.fetch(
            "SELECT * FROM schedules WHERE is_active AND next_run_at <= now() FOR UPDATE")
        for s in due:
            await enqueue(s.kind, site_id=s.site_id, **s.payload)
            await conn.execute(
                "UPDATE schedules SET last_run_at = now(), next_run_at = $2 WHERE id = $1",
                s.id, croniter(s.cron, now(), tz=s.timezone).get_next(datetime))
```

**Crawls are staggered, not simultaneous.** Fifteen sites crawling at 02:00 would saturate the
connection and get the IP throttled. The scheduler spreads them across a 4-hour window,
deterministically by site ID so the ordering is stable week to week:

```python
offset_minutes = int(hashlib.sha256(site.id.bytes).hexdigest()[:8], 16) % 240
```

### Progress reporting

Long jobs write progress to `jobs.progress` and `NOTIFY` so the UI updates live (§15):

```python
await job.progress(pct=34, detail="612 / 1,842 pages")
# → UPDATE jobs SET progress = $1 WHERE id = $2
# → NOTIFY job_progress, '{"job_id":"…","pct":34,…}'
```

Throttled to one update per 2 seconds. A crawler emitting a notify per page would generate
1,800 events and drown the SSE stream.

---

## §25. Queue System

### Postgres, not Redis

| Option | Verdict |
|---|---|
| **Redis + Celery** | The industry default. Adds a service, a second persistence story, and a class of bug where a job is acked in Redis but its transaction rolled back in Postgres. |
| RabbitMQ | Excellent routing. Heavy for ~200 jobs/day. |
| Temporal | Best-in-class durability. Two extra services and a server. Wildly disproportionate here. |
| **Postgres `SKIP LOCKED`** | No new service. Enqueue is *transactional with the data change*. Throughput ~1,000 jobs/sec — 100× headroom. |

**Recommendation: Postgres.** The transactional argument is the real one. `INSERT INTO jobs`
inside the same transaction as the row change means a job can never reference data that was
rolled back — the commonest and nastiest Redis+Postgres failure mode. At this scale Redis
would be pure operational cost with no benefit.

### Dequeue

```sql
UPDATE jobs
SET    status = 'running',
       locked_by = $1,
       locked_at = now(),
       lease_expires_at = now() + interval '30 minutes',
       attempts = attempts + 1,
       started_at = COALESCE(started_at, now())
WHERE  id = (
    SELECT id FROM jobs
    WHERE  status = 'queued'
      AND  queue  = $2
      AND  run_after <= now()
    ORDER BY priority, run_after
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING *;
```

`FOR UPDATE SKIP LOCKED` is the whole mechanism: concurrent workers each grab a different row
without blocking. The partial index from §13.8 keeps it an index scan over queued rows only.

### Lease-based recovery

Workers hold a **lease**, not a lock. If a worker is killed (Ctrl-C, OOM, laptop sleep — all
routine on a local machine), its job is reclaimed:

```sql
-- reclaim sweep, every 60 s
UPDATE jobs
SET    status = 'queued', locked_by = NULL, locked_at = NULL, lease_expires_at = NULL
WHERE  status = 'running'
  AND  lease_expires_at < now();
```

Long jobs extend their lease via heartbeat every 60 seconds. A crawl that legitimately takes
40 minutes keeps its lease; a crawl whose worker died loses it within 30 minutes.

**This is why laptop sleep is a first-class concern.** A hosted worker rarely vanishes
mid-job; a MacBook lid closing at 02:15 does it every week. Leases make that a non-event.

### Retry and dead-lettering

```python
BACKOFF = [60, 300, 1800]          # 1 min, 5 min, 30 min

async def on_failure(job: Job, exc: Exception):
    if isinstance(exc, PermanentError) or job.attempts >= job.max_attempts:
        await mark_dead(job, str(exc))
        await notify(job.org_id, kind="job_failed", severity="warning",
                     title=f"{job.kind} failed", body=str(exc)[:500],
                     link=f"/settings/jobs/{job.id}")
        return
    await conn.execute(
        "UPDATE jobs SET status='queued', run_after = now() + $2::interval, "
        "error = $3, locked_by = NULL WHERE id = $1",
        job.id, f"{BACKOFF[job.attempts - 1]} seconds", str(exc)[:2000])
```

**Errors are classified, not blanket-retried:**

| Class | Examples | Behaviour |
|---|---|---|
| `TransientError` | timeout, 503, connection reset | Retry with backoff |
| `QuotaError` | Google 429 | Requeue with `run_after` = quota reset time; not counted as an attempt |
| `PermanentError` | 404 property, invalid config, revoked token | Dead-letter immediately, notify |

Retrying a revoked OAuth token three times just delays telling the user something they must
fix by hand. `QuotaError` not consuming an attempt is equally important — a quota pause is
not a failure.

### Idempotency

Every handler must be safe to run twice; a lease can expire mid-work and the job re-run.

- `gsc_sync` — `INSERT … ON CONFLICT DO UPDATE`, keyed on the natural PK
- `crawl_site` — new `crawls` row each time; `pages` upserted on `(site_id, url_hash)`
- `embed_pages` — `content_hash` short-circuit (§20) makes a re-run nearly free
- `monthly_report` — `UNIQUE (site_id, kind, period_start)`; a re-run updates the draft
- `generate_draft` — creates a new `drafts.version`, never overwrites

### Observability

```
GET /v1/orgs/{org}/jobs?status=dead          # what needs attention
GET /v1/orgs/{org}/jobs/stream               # live progress (SSE)
```

Plus a health query the maintenance job runs nightly:

```sql
SELECT queue, status, count(*),
       max(now() - created_at) FILTER (WHERE status = 'queued') AS oldest_wait
FROM jobs
WHERE created_at > now() - interval '24 hours'
GROUP BY queue, status;
```

An `oldest_wait` above 30 minutes on any queue means a worker is wedged, and raises a
notification.

---

## §26. Webhook Architecture

### Inbound

Only one source in the default build: **WordPress**.

```
POST /v1/webhooks/wordpress/{site_id}
X-SEOOS-Signature: sha256=<hmac>
```

```python
async def verify(site_id: UUID, body: bytes, sig: str) -> bool:
    secret = await get_webhook_secret(site_id)          # per-site, generated on connect
    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)           # constant-time
```

| Event | Action |
|---|---|
| `post.published` | Enqueue a crawl of that URL; link it to a `publication` if it matches a draft |
| `post.updated` | Re-crawl and re-embed that page |
| `post.deleted` | Mark the page `is_gone`, prune its embeddings |

Handlers **enqueue and return 200 immediately**. Doing work inside the request means WordPress
times out and retries, producing duplicates. Replay is defended by storing a delivery ID for
24 hours.

### Outbound

Fires to a user-supplied URL — Slack, n8n, a custom endpoint. Nothing is required for the
platform to work; this is an escape hatch for agencies with existing workflows.

```sql
CREATE TABLE webhook_endpoints (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    url         text NOT NULL,
    secret      text NOT NULL,
    events      text[] NOT NULL,
    is_active   boolean NOT NULL DEFAULT true,
    failure_count smallint NOT NULL DEFAULT 0,
    disabled_at timestamptz
);

CREATE TABLE webhook_deliveries (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint_id   uuid NOT NULL REFERENCES webhook_endpoints(id) ON DELETE CASCADE,
    event         text NOT NULL,
    payload       jsonb NOT NULL,
    status_code   smallint,
    attempts      smallint NOT NULL DEFAULT 0,
    delivered_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);
```

Events: `crawl.finished`, `issue.critical_found`, `report.ready`, `ranking.dropped`,
`draft.generated`, `job.failed`.

Signed the same way as inbound (HMAC-SHA256 over the body), delivered through the job queue
with the same backoff. **20 consecutive failures disables the endpoint** and notifies — an
endpoint that has been dead for a week should stop consuming worker capacity.

---

## §27. Rate Limiting

### The binding constraint is upstream, not users

This is a local tool with a handful of users. Nobody is DDoSing it. The limits that actually
matter are the ones **we** must respect — Google's quotas, and the politeness the crawler owes
every site it touches.

### Layer 1 — Google API quotas

Handled by a token-bucket limiter per API and per property, with the quota state persisted so
a worker restart doesn't reset it.

| API | Documented limit | Configured budget |
|---|---|---|
| Search Console | ~1,200 QPM/site, 25,000 rows/request | 600 QPM, 2 concurrent |
| GA4 Data API | token-based, ~25,000/day/property | 60% of daily budget, 4 concurrent |
| Google Ads (Keyword Planner) | per developer token | 1 req/sec |
| Indexing API | 200 URLs/day/project | 180/day |

*(Google publishes and changes these; §38 flags them for re-verification before build.)*

```python
class QuotaLimiter:
    """Persisted token bucket. Survives worker restarts."""
    async def acquire(self, api: str, key: str, cost: int = 1):
        while True:
            ok, wait = await self._try_consume(api, key, cost)
            if ok:
                return
            raise QuotaError(retry_after=wait)   # requeues the job, no attempt consumed
```

Deliberately **60% of the documented budget**, not 95%. Headroom means a manual "Sync now"
during the day never competes with the nightly scheduled sync, and a Google-side quota change
doesn't immediately break everything.

### Layer 2 — Crawler politeness

Non-negotiable. This is someone else's server.

```python
CRAWL_DEFAULTS = {
    "delay_ms": 250,               # 4 req/s per host, before jitter
    "max_concurrent_per_host": 2,
    "respect_robots": True,
    "respect_crawl_delay": True,   # robots.txt Crawl-delay overrides ours
    "user_agent": "SEO-OS/1.0 (+https://growleadsagency.com/bot)",
    "timeout_s": 20,
    "max_retries": 2,
}
```

- **`robots.txt` is obeyed, always.** Not configurable off. A tool that ignores robots.txt is
  a liability for the agency running it.
- **Adaptive backoff:** three consecutive 429s or 503s from a host doubles the delay for the
  rest of that crawl.
- **Identifiable user agent** with a contact URL, so a site owner who sees the traffic can
  find out what it is.
- **Competitor crawls are capped** at 500 pages and run at half rate. Crawling a competitor
  aggressively is both rude and a good way to get the agency's IP blocked.

### Layer 3 — SERP fetching (`SerpProvider`)

The tightest limit in the system and the one with real consequences.

```python
class SerpProvider(Protocol):
    async def fetch(self, query: str, *, location: str, device: str) -> SerpResult: ...

class LocalScraper:
    """Default. $0. Hard-capped and deliberately slow."""
    DAILY_CAP = 200
    MIN_DELAY_S = 12                # ~5/min at absolute most
    JITTER_S = (4, 11)

class ApifyProvider:
    """Opt-in. User's own token, user's own bill. Off by default."""
    def __init__(self, token: str, monthly_cap: int): ...
```

**The 200/day cap is enforced in code, not documented as a guideline.** Exceeding it produces
CAPTCHAs, which produce garbage data that silently pollutes `rank_history` — worse than no
data. When the cap is hit the job requeues for the next day and the UI says so.

**GSC is always preferred where it can answer.** Before any SERP fetch, the resolver checks
whether the query already has GSC position data for a site we own. If it does, the SERP fetch
is skipped entirely. Most rank questions never touch a scraper:

```python
async def get_position(site_id, query, date):
    gsc = await gsc_position(site_id, query, date)
    if gsc is not None:
        return gsc, "gsc"                     # measured — always wins
    return await serp_provider.fetch(query), "serp"
```

### Layer 4 — Application

Present but generous, because the threat model is accident rather than abuse:

| Endpoint class | Limit |
|---|---|
| Read endpoints | 300/min per session |
| Mutations | 60/min per session |
| Job enqueue | 20/min per org |
| Chat | 20/min per session (Ollama serialises anyway) |
| Portal token attempts | 10/hour per IP |

The portal limit is the only genuinely security-motivated one — the token is the sole secret
(§16).

---

## §28. Multi Tenant Architecture

### Tenancy model

```
Organization  (the agency)
  └── Client  (Acme Corporation)
        └── Site  (acme.com, blog.acme.com)
```

Every tenant-scoped table carries `org_id`, even where derivable. §14 defends the
denormalisation; the payoff appears here.

### Isolation strategy

| Option | Verdict |
|---|---|
| Separate database per tenant | Perfect isolation. Absurd for a local single-agency tool — 15 databases, 15 migration runs. |
| Schema per tenant | Good isolation, but migrations multiply and cross-client queries (the whole dashboard) become unions. |
| **Shared schema + `org_id` + RLS** | One database, one migration path, cross-client queries are trivial. Isolation enforced by the database rather than by discipline. |

**Recommendation: shared schema with RLS.** The cross-client dashboard (§11) is a primary
feature, and it is a plain `GROUP BY org_id` here versus a union across schemas otherwise.
RLS supplies the isolation that schema separation would have given.

### Two enforcement layers

**Layer 1 — application.** Every query goes through a repository that requires a `Principal`.
There is no way to construct a query without one; the type system enforces it.

**Layer 2 — Postgres RLS.** The backstop. Even a raw SQL string with a missing `WHERE` clause
cannot cross a tenant boundary.

```sql
ALTER TABLE sites            ENABLE ROW LEVEL SECURITY;
ALTER TABLE gsc_daily        ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues           ENABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings       ENABLE ROW LEVEL SECURITY;
-- …every tenant-scoped table

CREATE POLICY tenant_isolation ON sites
    USING (org_id = current_setting('app.current_org_id', true)::uuid);
```

Set per transaction (§16):

```python
async with db.transaction() as tx:
    await tx.execute("SELECT set_config('app.current_org_id', $1, true)", p.org_id)
    await tx.execute("SELECT set_config('app.current_role',   $1, true)", p.role)
```

**`set_config(..., true)` scopes the setting to the transaction.** With connection pooling
this is the difference between correct isolation and a request inheriting the previous
request's tenant — the single most dangerous bug this architecture can have, and the reason
it is called out here rather than left implicit.

### The `client_viewer` case

The one role that is scoped *below* org level, and the only one exposed to people outside the
agency. It gets its own policy:

```sql
CREATE POLICY client_viewer_sites ON sites FOR SELECT
    USING (
        org_id = current_setting('app.current_org_id', true)::uuid
        AND (
            current_setting('app.current_role', true) IS DISTINCT FROM 'client_viewer'
            OR client_id = current_setting('app.current_client_id', true)::uuid
        )
    );
```

A bug that leaks another client's data to a client portal is the worst failure this product
can have — it is an incident with the agency's own customers. Hence: enforced in the API,
enforced again in RLS, and covered by a dedicated test suite (§48) that asserts a
`client_viewer` principal cannot read another client's rows through *any* endpoint.

### The worker's privileged path

Background jobs have no HTTP session. They connect as a role that bypasses RLS, and set the
org context explicitly per job:

```python
async def run_job(job: Job):
    async with db.transaction(role="worker") as tx:
        if job.org_id:
            await tx.execute("SELECT set_config('app.current_org_id', $1, true)", job.org_id)
        await HANDLERS[job.kind](job, tx)
```

`jobs.org_id` is set at enqueue time from the enqueuing principal. A job cannot be created
without one except for genuinely global maintenance jobs (`prune_storage`,
`create_partitions`), which are enqueued only by the scheduler.

### Cross-tenant query paths — the exhaustive list

Three, all deliberate, all org-scoped:

1. **Cross-client dashboard** (`/`) — aggregates across clients within one org
2. **Action plan** (`/action-plan`) — same
3. **Maintenance jobs** — no org context; touch only non-tenant tables

Any fourth is a bug. The test suite asserts that no repository method returns rows from more
than one `org_id` unless it is one of these three call sites.

### Noisy-neighbour containment

Even within one agency, one client can starve the others:

| Risk | Containment |
|---|---|
| One huge site monopolises crawl workers | `crawl_config.max_pages` default 5,000; per-site concurrency 1 |
| One client's AI jobs block everyone | `ai` queue is FIFO with priority; user-triggered jobs get priority 50, scheduled 100 |
| One client's GSC sync exhausts quota | Quota buckets are keyed per property, not per org |
| One client's data dominates the disk | Retention is per-site (§23) |

Priority 50 for user-triggered work is the one that matters day to day: when Priya clicks
"Crawl now," it jumps ahead of the nightly queue rather than waiting behind fourteen scheduled
jobs.

---

[← 07 AI Architecture](07-ai-architecture.md) · [Index](../README.md) · [Next: 09 — Security & Ops →](09-security-ops.md)
