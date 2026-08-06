# 03 — User Journeys

Section §7. [← Back to index](../README.md)

---

## §7. Complete User Journey

Six journeys, in the order a real user encounters them. Each names the screens touched, the
background jobs triggered, and the failure modes that must be designed for.

---

### Journey 1 — First run (Sam, agency owner, day 0)

**Goal: from empty folder to a real client's data on screen, in under 30 minutes.**

The riskiest journey in the product. If `setup.sh` fails, Persona 4 (Sneha, freelancer) has
nobody to ask and never comes back. Treat first-run reliability as a feature.

```
1. git clone / download → cd into folder
2. ./setup.sh
     ├─ checks: docker, python3, node — reports what's missing with the fix command
     ├─ pulls Ollama models: qwen3.5:9b (~5.5 GB), nomic-embed-text (~275 MB)
     ├─ docker compose up -d postgres
     ├─ runs migrations
     ├─ installs node + python deps
     └─ writes .env with generated secrets
     [8–20 min, mostly the model download. Progress shown per step.]

3. ./run.sh  →  opens http://localhost:3000

4. Onboarding wizard, 4 steps:
     Step 1  Create organization        "Acme Agency"
     Step 2  Connect Google account     OAuth → consent screen
     Step 3  Pick properties            lists every GSC + GA4 property you can access
     Step 4  Create first client        name it, assign properties, set brand voice (optional)

5. Initial sync fires automatically (background):
     ├─ job: gsc_backfill      pulls 16 months of Search Console history
     ├─ job: ga4_backfill      pulls 16 months of GA4
     ├─ job: crawl_site        first full crawl
     └─ job: lighthouse_run    Core Web Vitals for top 20 pages by impressions
     [Dashboard shows live progress per job. Usable at ~40% — partial data renders.]

6. First insight appears within ~3 minutes:
     "18 queries are ranking 5–15 with above-average impressions and below-average CTR."
```

**Failure modes designed for**

| Failure | Handling |
|---|---|
| Docker not installed | `setup.sh` detects and prints the exact install command; does not continue |
| Ollama model download interrupted | Resumable; re-running `setup.sh` skips what's already pulled |
| OAuth consent rejected | Wizard stays on step 2 with a plain-English explanation of the scopes and why each is needed |
| No GSC properties on the account | Explicit message — this is the qualifying condition (§3); tell them plainly rather than showing an empty list |
| GSC backfill hits quota | Job pauses, resumes automatically next window; dashboard says "syncing, 8 of 16 months" |
| Port 3000 in use | `run.sh` detects and offers 3001 |

**Success criterion:** a real GSC number visible on screen within 30 minutes of download,
without reading documentation.

---

### Journey 2 — The Monday operating loop (Priya, SEO strategist, weekly)

**Goal: know what changed across 8 client sites and start fixing, in under 20 minutes.**

This is the journey that determines whether the product gets daily use or becomes shelfware.

```
Sunday 02:00  — scheduled jobs run unattended
   ├─ gsc_sync          incremental, all sites
   ├─ ga4_sync          incremental, all sites
   ├─ crawl_site        full crawl, all sites, staggered
   ├─ lighthouse_run    top pages per site
   ├─ diff_crawl        compares to last week
   └─ weekly_report     narrative generated per site

Monday 09:00  — Priya opens the dashboard
   │
   ├─ Cross-client view: 8 site cards, sorted by "needs attention"
   │     Each card: health score + delta, clicks Δ, top issue, unread flag
   │
   ├─ Two cards are red:
   │     "Acme — health 71 (−12). 14 new 404s from /blog/*"
   │     "Nova — clicks −23% WoW. 3 queries lost top-10."
   │
   ├─ Clicks Acme → Technical Scanner → filtered to "New this week"
   │     14 URLs, all from one directory. Cause: a category slug changed.
   │     AI remediation: "Add 301s from old → new. Bulk redirect map below."
   │     → Exports the redirect map, sends to Acme's developer. [4 min]
   │
   ├─ Clicks Nova → Chat Assistant
   │     "Why did clicks drop 23% last week?"
   │     Answer: the three lost queries all point to /pricing, which returned
   │     500 for ~14 hours on Thursday per crawl history; position recovered
   │     by Saturday but impressions haven't. Cites the crawl rows and GSC dates.
   │     → No action needed. Notes it for the monthly report. [3 min]
   │
   └─ Action Plan tab → cross-client "10 things to do this week"
         Assigns 4 to herself, 3 to Rahul (content), 3 to the dev. [6 min]

Total: ~15 minutes to full situational awareness across 8 clients.
```

**The design requirement this creates:** the dashboard must open on **diffs, not state**.
Showing the same 400 technical issues every week trains the user to ignore it. Showing the
14 that are new makes it the first tab opened every Monday.

---

### Journey 3 — Content, brief to published (Rahul, writer)

**Goal: a published post that went brief → outline → draft → edit → WordPress without
leaving the tool.**

```
Week 1 — Priya plans
  Content Planner → Acme → sees cluster "commercial refrigeration maintenance"
    · 11 queries · 4,200 impressions/mo · avg position 14 · CTR 0.6%
    · Existing coverage: none
    · Opportunity score: 87/100  ← highest unaddressed cluster
  → "Generate brief"

  Brief Builder runs (background, ~40 s):
    ├─ pulls the 11 GSC queries + intent classification
    ├─ crawls top 5 ranking competitor pages for the head query
    ├─ extracts entities via Wikidata; diffs against Acme's existing content
    ├─ retrieves Acme brand voice from AI memory (§22)
    ├─ finds 6 internal link targets by embedding similarity
    └─ proposes an outline: H1 + 7 H2s with intent notes per section

  Priya edits the outline (removes one H2, reorders two), approves. [6 min]
  Assigns to Rahul.

Week 1 — Rahul writes
  Opens the brief. Everything is there: target queries, outline, entities to
  cover, internal links to place, tone rules, word target, competitor gaps.

  → "Generate draft"
  Blog Generator runs section by section (§17). ~3–5 min for 1,800 words.
  Each section receives only its outline node + the previous section's last
  paragraph — never the whole document. This is why 9B works here.

  Rahul edits in the built-in editor. [35 min — this is the honest number;
  the tool removes the blank page and the research, not the craft.]

  Right rail shows live: query coverage, entity coverage, internal links
  placed, readability, word count vs target.

  → "Generate schema"  → Article JSON-LD, validated
  → "Publish to WordPress" → creates a draft post with schema in the head

Week 5 — the loop closes
  The post's row in Content appears with its own GSC data:
  impressions 340, clicks 12, avg position 18.
  → "Suggest improvements" reads the actual ranking queries and proposes
    specific edits. The post is an asset that gets iterated, not shipped and forgotten.
```

**The honest note in this journey:** 35 minutes of editing is not zero. The product's claim
is that it removes research, briefing, structuring, and the blank page — not that it removes
writing. §39 states the same thing in cost terms.

---

### Journey 4 — Monthly reporting (Sam, month end)

**Goal: 20 hours of reporting across 15 clients becomes 3.**

```
1st of month, 03:00 — worker generates all 15 reports unattended
  Per site: GSC MoM + YoY, GA4 conversions, rankings movement, technical
  health delta, content published, links gained/lost, next month's plan.
  Report Narrator writes the executive summary and the "what this means" prose.

09:00 — Sam opens Reports
  15 reports listed, status "Draft — needs review"

  Per report (~8 min each):
    ├─ reads the AI summary
    ├─ edits 2–3 sentences where the AI's causal claim is too confident
    │     (design requirement: every claim in a report must be traceable to
    │      the rows that produced it, so this check is fast)
    ├─ adds one line of agency context the data can't know
    │     ("Q3 budget was paused for 3 weeks")
    └─ Approve → PDF + shareable link generated

  Client-facing output is white-labelled: agency logo, client colours,
  no mention of the tool.

Total: ~2.5 hours for 15 clients. Was ~20.
```

**Design requirement this creates:** the AI must never state a cause it cannot evidence.
Reports say "clicks fell 23%; /pricing returned 500 errors for 14 hours on 14 Nov" — not
"clicks fell because of a server issue." Correlation gets presented as correlation. This is
what makes the 8-minute review possible instead of a 30-minute fact-check.

---

### Journey 5 — The client view (read-only, `client_viewer` role)

**Goal: the client sees their own data, live, and nothing else.**

```
Sam → Client Settings → Sharing → "Create client link"
   ├─ scoped to exactly one client's sites
   ├─ role: client_viewer (read-only, enforced by RLS — §28)
   ├─ optional passcode, optional expiry
   └─ sections toggled on/off per client

Client opens the link:
   ├─ White-labelled. Agency branding. No tool name anywhere.
   ├─ Sees: traffic, rankings, health score, published content, past reports
   ├─ Cannot see: other clients, settings, the action plan, cost data,
   │              raw crawl output, AI configuration
   └─ Can: download past reports, view live dashboard
```

**Why this matters commercially:** it is the difference between "here's a PDF once a month"
and "here's a live dashboard you can open any time," which is an easy retainer-defending
upgrade at zero marginal cost.

**Security requirement:** `client_viewer` is enforced twice — once at the API layer and again
by Postgres row-level security, so a bug in the API layer cannot leak another client's data.
See §28 and §29.

---

### Journey 6 — Onboarding a new client (recurring, ~10 minutes)

```
Clients → "Add client"
  Step 1  Name, industry, primary domain
  Step 2  Connect properties
            · GSC property   [dropdown of properties this Google account can access]
            · GA4 property   [dropdown]
            · GBP location   [optional]
  Step 3  Brand voice (optional but recommended)
            · paste 2–3 existing pages, or fill a short form
            · → stored as an org-scoped memory (§22), used by every content module
  Step 4  Crawl configuration
            · start URL, max pages, include/exclude patterns, crawl rate
            · defaults are sensible; most users never open this
  Step 5  Competitors (optional)
            · up to 5 domains to crawl for gap analysis
  → Create

Background: backfill + first crawl fire immediately. Usable in ~3 minutes,
complete in ~15 depending on site size.
```

**The friction point to watch:** step 2 fails if the agency's Google account doesn't have
access to the client's property. The wizard must detect this and produce the exact text to
send the client ("ask them to add `you@your-agency.com` as a *Restricted* user in
Search Console"), rather than an empty dropdown.

---

### Cross-cutting: what happens when things break

| Situation | User-visible behaviour |
|---|---|
| Ollama not running | Banner: "AI features unavailable — start Ollama with `ollama serve`." Data modules keep working. |
| Crawl blocked by robots.txt | Site card shows "Crawl restricted" with which paths were disallowed |
| GSC token expired | Client card shows "Reconnect Google" with a one-click re-auth; other clients unaffected |
| Google quota exhausted | Job pauses and auto-resumes next window; UI says "syncing resumes at 00:00 UTC" |
| Job crashed | Retried 3× with backoff, then dead-lettered and surfaced in Notifications with the error |
| Postgres down | The app cannot start; `run.sh` reports it and offers `docker compose up -d postgres` |
| Disk full from crawl artifacts | Retention policy (§23) prunes automatically; warning at 80% |

**The principle:** a failure in one client, one integration, or one module never takes down
the others. Every external dependency is isolated behind a job that can fail alone.

---

[← 02 Features](02-features.md) · [Index](../README.md) · [Next: 04 — UI/UX →](04-ui-ux.md)
