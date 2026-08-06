# 11 — Costs, Scaling & Performance

Sections §38–§44. [← Back to index](../README.md)

---

## §38. API Cost Breakdown

### Every external dependency, and what it costs

| API | Cost | Limit | What breaks at the limit |
|---|---|---|---|
| Google Search Console | **$0** | ~1,200 QPM/site; 25,000 rows/request; 16 months history | Sync slows; auto-resumes |
| Google Analytics 4 Data | **$0** | Token-based, ~25,000/day/property | Sync pauses to next window |
| Google Business Profile | **$0** | Low default; needs a quota request | GBP module unavailable |
| Google Ads (Keyword Planner) | **$0** | Requires an approved developer token | Volume data absent; GSC impressions used as proxy |
| Google Indexing API | **$0** | 200 URLs/day/project | Manual submission |
| Wikidata / Wikipedia | **$0** | Courtesy limits, no key | Entity module degrades |
| Common Crawl | **$0** | Batch dataset, not an API | Competitor backlinks unavailable |
| Lighthouse (local CLI) | **$0** | **None — runs on your machine** | — |
| Own crawler | **$0** | Politeness limits we impose (§27) | — |
| Ollama / Qwen 3.5 | **$0** | GPU throughput only | Inference queues |
| **Total** | **$0/month** | | |

> ⚠️ **Google publishes and revises these quotas.** The numbers above are the planning basis,
> not a guarantee. Re-verify against Google's current documentation before implementation, and
> encode the verified values in `packages/core/quota.py` rather than in prose.

### The quota that actually binds: how many clients fit

The interesting question isn't "what does it cost" (nothing) but **"how many client sites can
one instance serve before a free quota becomes the ceiling?"**

**Search Console.** A full 16-month backfill for one site is ~480 requests (16 months × 30
days, paginated at 25,000 rows). At 1,200 QPM that's ~25 seconds of quota. Nightly incremental
sync is ~5 requests per site. **Practical ceiling: hundreds of sites.** Not the constraint.

**GA4.** The real one. The Data API charges *tokens*, not requests — a complex query with many
dimensions costs more. Budget ~25,000 tokens/day per property; a nightly sync pulling landing
page × channel × date for one site costs roughly 2,000–4,000 tokens.

```
Daily GA4 budget per property   ≈ 25,000 tokens
Nightly sync cost per site      ≈ 3,000 tokens
Headroom per site               ≈ 8× the nightly sync
```

Quota is **per property**, so adding clients adds quota. It does not aggregate into a shared
pool. **Not a scaling ceiling either.**

**The genuine ceiling is wall-clock time, not quota.** Fifteen sites × (crawl 5–40 min +
embed 1–6 min + AI analysis 1–3 min) must fit in the nightly window. §42 works the arithmetic.

### Optional paid adapters — off by default

Neither is required. Both exist behind the interfaces in §17 and §27.

**`ApifyProvider`** — replaces `LocalScraper` for competitor SERP data.

| Scale | SERPs/month | Estimated cost |
|---|---|---|
| 10 clients × 30 kw, weekly | ~1,300 | $0 — inside the free credit |
| 25 clients × 40 kw, weekly | ~4,300 | ~$15–20 |
| 50 clients × 50 kw, weekly | ~10,800 | ~$49 (paid tier) |

Verify Apify's current per-result pricing and free-credit allowance before enabling. Cost
scales linearly with `clients × keywords × frequency`, so the controls in §27 — weekly cadence,
GSC-first resolution, caching, and a hard monthly cap — are the difference between $15 and
$150.

**`RemoteProvider`** — a frontier LLM for specific deliverables. Billed to the user's own key,
enabled per task kind (§12.13). For calibration, a 2,000-word article through a mid-tier
frontier model costs roughly $0.15–0.30 — so occasional use for a flagship client piece is
trivial, and defaulting everything to it would cost ~$8/site/month.

### What genuinely cannot be bought at $0

Stated plainly, because the rest of this document is optimistic and these three are not:

| Missing | Why no free source exists | Consequence |
|---|---|---|
| Competitors' ranking keywords | Requires a proprietary keyword-position index | Content Gap gives *topical* gaps, not keyword gaps (§5.5) |
| Competitors' backlinks | Requires a proprietary link index | Backlink Tracker covers your own sites only (§5.16) |
| High-volume SERP feature data | Google rate-limits automated queries | AI Overview module capped at ~200 queries/day (§5.15) |

---

## §39. AI Cost Breakdown

### Cost is time, not money

Local inference has no per-token price. The budget is **wall-clock seconds on one GPU**, and
the `ai` queue runs a single worker (§17), so everything serialises.

### Measured expectations on the M5

To be verified during build and recorded in `packages/agents/BENCHMARKS.md`:

| Operation | Tokens (in/out) | Time |
|---|---|---|
| Issue explanation (schema, `think=False`) | 800 / 200 | ~2–4 s |
| Cluster label | 400 / 40 | ~0.8–1.5 s |
| Intent classification | 200 / 20 | ~0.5 s |
| Blog section (~300 words) | 900 / 400 | ~8–14 s |
| Editor pass on a section | 1,200 / 400 | ~10–16 s |
| Report narrative (`think=True`) | 3,000 / 800 | ~25–45 s |
| Chat answer (`think=True` + RAG) | 4,000 / 400 | ~15–30 s |
| Embedding, batch of 32 | — | ~0.4 s |

**Reasoning disabled is the single biggest lever.** `Growleads L.S` measured 27 s → 0.8 s on a
trivial structured prompt. Across a nightly run of ~200 structured calls that is the difference
between roughly 90 minutes and 5 minutes.

### Nightly AI budget per site

| Job | Calls | Time |
|---|---|---|
| `analyse_issues` | 5–15 (only changed issues) | 20 s – 1 min |
| `embed_pages` | batched; 95% skipped by `content_hash` | 30 s – 90 s |
| `cluster_keywords` (weekly) | ~47 labels + 1 summary | 1–2 min |
| `suggest_links` (weekly) | 1 batched call | 40 s – 2 min |
| Dashboard summary | 1 | 15–25 s |
| **Nightly total per site** | | **~3–6 min** |

At 15 sites: **45–90 minutes of GPU time per night**, comfortably inside a 6-hour window
(§42).

On-demand work sits outside that budget: a blog draft is ~3–5 minutes, a monthly report ~2–4
minutes, a chat message ~15–30 seconds.

### The three optimisations that make this fit

**1. Don't call the model when code can answer.** The technical audit graph (§17) has five
nodes, of which two are model calls — and one is skipped entirely when nothing changed since
the last crawl. Loading, grouping, and persisting are SQL.

**2. `content_hash` short-circuit.** Re-embedding 1,800 unchanged pages weekly would cost ~25
minutes of GPU. Hashing chunks and skipping unchanged ones brings it under 90 seconds (§20).

**3. Cache generated narratives.** The dashboard's AI summary is written when the sync
finishes and stored on `agent_runs`. Generating it per page view would put a 20-second wait on
the most-visited screen in the product (§11).

### Electricity — the only real cost

An M5 under sustained inference draws roughly 30–45 W above idle. At ~90 minutes nightly:

```
0.04 kW × 1.5 h × 30 nights  ≈  1.8 kWh/month
At ₹8/kWh                    ≈  ₹15/month  (~$0.18)
```

**Under twenty rupees a month to run every AI feature for fifteen clients.** That is the
honest total, and it is the number worth quoting when someone asks what the AI costs.

---

## §40. Hosting Cost

| Component | Where | Cost |
|---|---|---|
| Application | Your Mac | $0 |
| Postgres | Docker, same machine | $0 |
| Ollama | Native, same machine | $0 |
| File storage | Local disk (~6.5 GB at 15 clients / 2 yr) | $0 |
| Backups | Local disk + wherever you copy them | $0 |
| CI | GitHub Actions free tier | $0 |
| Public tools site | Cloudflare Pages free tier | $0 |
| Domain (optional) | if you want a nice tools URL | ~$12/yr |
| **Total** | | **$0/month** |

### If you ever host it — the honest numbers

This is the section that keeps the $0 claim honest. Hosting for third parties breaks it, and
here is by how much (§51 covers whether that is ever worth doing):

| Component | Entry (≤50 orgs) | Notes |
|---|---|---|
| App server (4 vCPU / 8 GB) | ~$25/mo | Hetzner CPX31 or equivalent |
| Managed Postgres | ~$50/mo | Or self-hosted at ~$15 with your own backups |
| **GPU for inference** | **~$200–400/mo** | **The killer.** A local model needs a GPU per concurrent stream |
| Object storage | ~$5/mo | |
| Email (transactional) | ~$20/mo | Gmail SMTP doesn't scale to multi-tenant |
| Error tracking | ~$26/mo | |
| **Total** | **~$330–530/mo** | |

**The GPU line is what makes hosted local-AI uneconomic at small scale.** The alternative that
actually works: host the app, and require each customer to supply their own LLM API key
(`RemoteProvider`). Infrastructure drops to ~$100/month and the AI cost moves to the customer
entirely — which is the model §52 recommends if this is ever productised.

---

## §41. Monthly Cost Estimate

### The whole thing, at three scales

| | 5 clients | 15 clients | 50 clients |
|---|---|---|---|
| Google APIs | $0 | $0 | $0 |
| AI inference | $0 | $0 | $0 |
| Crawling | $0 | $0 | $0 |
| Lighthouse | $0 | $0 | $0 |
| Database | $0 | $0 | $0 |
| Queue | $0 | $0 | $0 |
| Hosting | $0 | $0 | $0 |
| Storage | $0 | $0 | $0 |
| Electricity | ~₹6 | ~₹15 | ~₹45 |
| **Total** | **~$0.07** | **~$0.18** | **~$0.55** |

### Against the stack it replaces

| Tool | Replaced by | Their cost |
|---|---|---|
| Ahrefs / Semrush | GSC API + own crawler + GSC links | $199–499/mo |
| Surfer / Clearscope | On-page checker + entity module | $89–199/mo |
| Screaming Frog | Own crawler | ~$22/mo |
| AgencyAnalytics | Report generator + client portal | $60–180/mo |
| An AI writing tool | Local blog pipeline | $49–99/mo |
| **Total replaced** | | **$419–999/mo** |
| **This** | | **~$0.18/mo** |

**Annual saving at 15 clients: roughly $5,000–12,000.** Which is the entire commercial argument
for building it, and it is worth restating that the saving is not the *only* argument — the
joined data (§2, Problem 2) and the client-data-stays-local pitch (§2, Problem 7) are things
the paid stack cannot offer at any price.

### What is lost for that saving

Restated once more, because a cost table without it is dishonest:

- Competitors' ranking keywords and backlink profiles
- SERP monitoring above ~200 queries/day
- Frontier-quality long-form prose in a single pass
- A vendor to call when something breaks

For an agency serving clients whose Search Console they can access, that trade is strongly
favourable. For a competitive-intelligence-led consultancy, it is not — and those users should
keep paying Ahrefs.

---

## §42. Scaling Strategy

### The real constraint is the nightly window

Not quota, not cost, not database size — **wall-clock time on one machine**.

```
Per site, nightly:
  gsc_sync            20 s –  4 min   ┐
  ga4_sync            15 s –  2 min   ├─ parallel, 2 sync workers
  crawl_site           5   – 40 min   ─── parallel, 4 crawl workers
  lighthouse_run       2   –  8 min   ─── shares crawl workers
  embed_pages         30 s –  6 min   ┐
  analyse_issues      20 s –  3 min   ├─ SERIAL, 1 ai worker
  cluster_keywords     1   –  3 min   │
  suggest_links        1   –  4 min   ┘
```

The `ai` queue is serial by design (one GPU). At ~4 minutes of AI per site:

| Sites | AI queue time | Fits a 6 h window? |
|---|---|---|
| 15 | ~60 min | ✅ comfortably |
| 30 | ~2 h | ✅ |
| 50 | ~3.5 h | ✅ |
| 80 | ~5.5 h | ⚠️ marginal |
| 100+ | ~7 h | ❌ |

**Practical ceiling on this hardware: ~60–80 client sites.** Well beyond what a 3–6 person
agency runs, which is the point.

### Scaling levers, in the order to reach for them

**1. Reduce AI work per site (free, immediate).**
- Analyse only *changed* issues — already the design (§17)
- Weekly rather than nightly clustering and link suggestions
- Skip embedding unchanged content — already the design (§20)

**2. Widen the window.** 02:00–08:00 is six hours; most agencies don't need results before 09:00.

**3. Stagger across the week.** Crawl a fifth of sites each weekday instead of all on Sunday.
Turns a 3.5-hour Sunday into 45 minutes a night.

**4. A bigger machine.** An M-series with 32–64 GB runs a 14B model *and* a larger context, or
two model instances for genuine AI parallelism. This is the highest-leverage upgrade and still
a one-time cost.

**5. Split the worker onto a second machine.** Postgres accepts connections from the LAN; a
second Mac or a Linux box with a GPU runs `apps/worker` and its own Ollama. The architecture
already supports it — the worker connects over the network, and `packages/` is shared.

**6. Only then: host it.** §40's numbers, §51's decision.

### Database scaling

| Concern | At what point | Mitigation |
|---|---|---|
| `gsc_daily` size | ~33M rows @ 15 clients / 2 yr | Already partitioned; detach partitions >16 months — GSC only retains 16 anyway, so the table is permanently capped |
| Query latency | >500 ms on dashboard views | Already materialised; refresh after sync, never on request |
| Vector search | >2M vectors | pgvector to ~1M comfortably; §21 gives the Qdrant triggers |
| Connection exhaustion | >60 connections | pgbouncer in transaction mode — but note it breaks `set_config(..., true)` unless carefully configured (§28) |
| Disk | >80% | Retention job (§23); prune crawl artefacts first |

**The partition-detach point deserves emphasis:** because Search Console itself only retains 16
months, the largest table in the system has a permanent size ceiling. It does not grow without
bound no matter how long the tool runs.

### What would need rewriting for true multi-tenant SaaS

Honest inventory, so the estimate isn't optimistic:

| Component | Reusable? |
|---|---|
| Database schema, RLS | ✅ Already multi-tenant |
| API, RBAC, auth | ✅ |
| Crawler, integrations, analysis | ✅ |
| Frontend | ✅ |
| Job queue | ⚠️ Fine to ~10k jobs/day; beyond that, shard by org |
| AI layer | ❌ **Local inference doesn't multi-tenant.** Either a GPU fleet or `RemoteProvider` with customer keys |
| Billing | ❌ Not built (tables reserved, §13.8) |
| Ops | ❌ Backups, monitoring, on-call, support |

**Roughly 80% reusable.** The AI layer is the genuine rewrite, and §52's BYO-key model is what
avoids it.

---

## §43. Performance Optimization

### Budgets

| Surface | p95 target | Why |
|---|---|---|
| Site dashboard | **< 300 ms** | Opened dozens of times a day |
| Cross-client dashboard | < 400 ms | Monday morning entry point |
| GSC query table (50 rows) | < 250 ms | Interactive filtering |
| Technical scanner | < 200 ms | Reads pre-computed `issues` |
| Chat, first token | < 3 s | Perceived responsiveness |
| Chat, complete | < 30 s | Streaming makes this tolerable |
| Report generation | < 5 min | Background job |
| Full crawl, 2,000 pages | < 25 min | Background job |

### Frontend

**Materialised views, not live aggregation.** Every dashboard widget reads a pre-computed view
refreshed by the worker (§13.9). This is the single decision that keeps the dashboard under
300 ms against a 33M-row table.

**Pre-generated AI narratives.** The dashboard summary is written when sync completes, not on
page view (§39).

**RSC streaming.** The shell and KPI cards render immediately; slower widgets stream in via
Suspense boundaries.

**Virtualised tables.** TanStack Virtual for GSC query tables — 3,412 rows render 20 DOM nodes.

**Route-level code splitting.** The chat interface and draft editor are the heaviest bundles
and are only loaded on their routes.

### Database

```sql
-- Every hot query path has a covering index. The four that matter:
CREATE INDEX ON gsc_daily (site_id, date DESC);                    -- time series
CREATE INDEX ON gsc_daily (site_id, query text_pattern_ops);       -- query lookup
CREATE INDEX ON issues (site_id, first_seen_at DESC) WHERE state = 'open';  -- "new this week"
CREATE INDEX jobs_dequeue ON jobs (queue, priority, run_after) WHERE status = 'queued';
```

- **Partition pruning:** date-bounded queries touch one or two monthly partitions.
- **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** so refreshes never block readers.
- **Connection pooling:** asyncpg pool, 10 for the API, 4 per worker.
- **`log_min_duration_statement=1000`** surfaces slow queries without manual profiling.

### Crawler

| Technique | Effect |
|---|---|
| `selectolax` over BeautifulSoup | 5–10× faster parsing |
| Async with per-host concurrency 2 | Throughput without rudeness |
| `HEAD` before `GET` for link checking | Skips body download for status checks |
| Conditional requests (`If-Modified-Since`) | 304 on unchanged pages skips parse *and* embed |
| Streaming JSONL output | Flat memory regardless of site size |
| Content-hash short-circuit | Skips ~95% of re-embedding |

**Conditional requests are underrated.** A weekly re-crawl of a mostly-static site returns 304
for most pages, which cascades — no parse, no diff, no re-embed. A 25-minute crawl becomes 6.

### AI

Covered in §39. The three levers restated: don't call the model when SQL can answer, keep
`think=False` for structured work, and cache anything a user might see more than once.

**Model residency:** `OLLAMA_KEEP_ALIVE=30m`. A cold model load is 6–10 seconds, which would
land on the Chat Assistant's first message of the day — the worst possible place for it.

### The opportunity score (referenced throughout)

```python
def opportunity_score(impressions, position, ctr, site_median_impressions) -> int:
    if not (5 <= position <= 20):
        return 0                                    # already won, or too far away
    volume    = min(impressions / max(site_median_impressions, 1), 3.0) / 3.0
    proximity = (20 - position) / 15                # closer to page 1 is worth more
    expected  = expected_ctr_for_position(position) # empirical curve
    ctr_gap   = max(0.0, (expected - ctr) / expected) if expected else 0.0
    return round(100 * (0.4 * volume + 0.35 * proximity + 0.25 * ctr_gap))
```

Computed in SQL over `mv_query_opportunities`, never by the model (§18 rule 5). The model
*explains* the score; it never invents it.

---

## §44. SEO Strategy for the platform

The platform is internal, so "SEO for the platform" means **SEO for the agency running it**, using
this tool as the engine. Three plays, all $0.

### Play 1 — The free tools site

Static, client-side only, on Cloudflare Pages' free tier. Every tool is a landing page that
ranks for a high-intent query and demonstrates competence.

| Tool | Target query | Why it works |
|---|---|---|
| JSON-LD schema generator | "schema markup generator" | High volume, commercial intent, evergreen |
| robots.txt tester | "robots.txt tester" | Google's own tool was retired — real gap |
| SERP snippet preview | "serp preview tool" | Used repeatedly, high return rate |
| Meta / OG preview | "open graph preview" | Shared between marketers |
| Hreflang generator | "hreflang generator" | Low competition, high intent |
| Sitemap XML validator | "sitemap validator" | |
| UTM builder | "utm builder" | Very high volume |
| Readability scorer | "readability checker" | |

Every tool runs entirely in the browser — no backend, no cost, no rate limit, and it works
offline. Each page carries `SoftwareApplication` + `FAQPage` schema and a single, honest CTA
to the agency.

**The strategic point:** these pages are dogfood. The agency's own site becomes a client of
the tool, and the content plan for the tools site is generated by the content planner.

### Play 2 — Programmatic comparison and guide pages

Generated by the content pipeline, reviewed by a human before publishing:

- "Ahrefs alternative for small agencies" — and comparable honest comparisons
- "How to use Search Console instead of a rank tracker" — the §1 argument as a guide
- "Free SEO tools for agencies" — with the tools site as the proof

The angle that differentiates: **the free-data thesis is a genuinely contrarian, defensible
content position.** Most SEO content assumes you need paid tools. An agency arguing —
credibly, with a working product — that Search Console is better than Ahrefs *for your own
clients* is memorable and linkable.

### Play 3 — GEO / LLM visibility

Increasingly people ask an assistant rather than a search engine. Optimising for citation:

| Tactic | Why |
|---|---|
| Structured, factual, well-cited pages | Assistants prefer content they can attribute |
| Explicit FAQ sections with direct answers | Matches how questions are asked |
| `Organization` + `SoftwareApplication` + `FAQPage` schema | Machine-readable entity signals |
| Wikidata-consistent entity naming | Entity resolution (module 14) applied to ourselves |
| Original data and specific numbers | Nothing gets cited like a number nobody else has |

The last one is the strongest and the most under-used. Publishing something like *"we measured
Qwen 3.5 9B at 0.8 s per structured SEO task with reasoning disabled, versus 27 s with it on"*
is an original, citable fact that no competitor has — and it costs nothing but honesty about
your own benchmarks.

### Measurement

The agency's own site is client #1 in the tool. The tools site is a second property. Both are
tracked in exactly the same dashboard as paying clients — which is the fastest possible
feedback loop on whether the product works, because the person who feels the pain is the
person who can fix the code.

---

[← 10 Deployment](10-deployment.md) · [Index](../README.md) · [Next: 12 — Roadmap →](12-roadmap.md)
