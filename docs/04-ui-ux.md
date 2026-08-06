# 04 — UI / UX

Sections §8–§12. [← Back to index](../README.md)

---

## §8. UI Screen List

31 screens across 7 groups. Each maps to a Next.js App Router route.

### Onboarding & auth (4)

| Screen | Route | Notes |
|---|---|---|
| Sign in | `/login` | Google OAuth only — no password to manage |
| Onboarding wizard | `/onboarding` | 4 steps, §7 Journey 1 |
| Connect Google | `/onboarding/google` | Consent + property picker |
| Add client | `/clients/new` | Also reachable later, §7 Journey 6 |

### Dashboards (3)

| Screen | Route | Notes |
|---|---|---|
| Cross-client overview | `/` | Agency home. Sorted by "needs attention" |
| Site dashboard | `/s/[site]` | The main working surface. §11 |
| Client portal | `/portal/[token]` | Read-only, white-labelled, `client_viewer` |

### Analytics (4)

| Screen | Route |
|---|---|
| Search Console | `/s/[site]/search-console` |
| GA4 | `/s/[site]/analytics` |
| Rankings | `/s/[site]/rankings` |
| Query → Page explorer | `/s/[site]/queries` |

### Technical (5)

| Screen | Route |
|---|---|
| Technical scanner | `/s/[site]/technical` |
| Issue detail | `/s/[site]/technical/[issue]` |
| Crawl history & diffs | `/s/[site]/technical/crawls` |
| Broken links | `/s/[site]/technical/links` |
| Website health | `/s/[site]/health` |

### Research & content (8)

| Screen | Route |
|---|---|
| Keyword clusters | `/s/[site]/keywords` |
| Topic clusters | `/s/[site]/topics` |
| Content planner | `/s/[site]/planner` |
| Content inventory | `/s/[site]/content` |
| Brief builder | `/s/[site]/content/brief/[id]` |
| Draft editor | `/s/[site]/content/draft/[id]` |
| Internal linking | `/s/[site]/linking` |
| Schema generator | `/s/[site]/schema` |

### Competitive & links (3)

| Screen | Route |
|---|---|
| Competitors | `/s/[site]/competitors` |
| Content gap | `/s/[site]/gap` |
| Backlinks | `/s/[site]/backlinks` |

### Platform (4)

| Screen | Route |
|---|---|
| AI chat | `/s/[site]/chat` |
| Reports | `/s/[site]/reports` |
| Action plan | `/action-plan` |
| Settings | `/settings/*` |

---

## §9. Navigation Structure

Three levels. The **client switcher is global** and persists across every screen — an agency
user changes client far more often than they change module.

```
┌─ Top bar (always visible) ──────────────────────────────────────────┐
│  [Logo]  [Client ▾]  [Site ▾]     ⌘K search   🔔 12   [Avatar ▾]    │
└─────────────────────────────────────────────────────────────────────┘
   │                                                        │
   ├─ Client ▾  ── all clients / Acme / Nova / …            ├─ Profile
   │              + Add client                              ├─ Org settings
   │                                                        ├─ Integrations
   └─ Site ▾   ── acme.com / blog.acme.com                  ├─ AI providers
                  + Add site                                └─ Sign out
```

**Routing rule:** `/s/[site]/*` scopes to one site. `/` and `/action-plan` are cross-client.
Switching client on a site-scoped page navigates to the same module for the new client's
primary site — so the module you're working in survives a client switch. This is the single
most important navigation behaviour for Persona 2 (Priya, 8 clients).

**Keyboard:** `⌘K` opens a command palette — jump to any client, site, module, or query.
Power users navigate almost entirely from it.

---

## §10. Sidebar Structure

Collapsible, grouped, with live counts. Counts are what make it useful — a badge on
Technical means Priya knows there's something new before clicking.

```
┌──────────────────────────┐
│ ◈ Acme Corporation       │   ← current client
│   acme.com               │   ← current site
├──────────────────────────┤
│ ⌂  Dashboard             │
├─ ANALYTICS ──────────────┤
│ ⌕  Search Console        │
│ ▲  Analytics (GA4)       │
│ ↑  Rankings         ▲3   │   ← 3 queries moved into top 10
│ ⌗  Queries               │
├─ TECHNICAL ──────────────┤
│ ⚙  Scanner          ●14  │   ← 14 new issues this week
│ ⚕  Health           71   │   ← current score, red if dropped
│ ⛓  Broken links     ●2   │
├─ RESEARCH ───────────────┤
│ ✦  Keywords              │
│ ◎  Topics                │
│ ⊞  Content gap           │
│ ⚑  Competitors           │
│ ⚭  Backlinks             │
├─ CONTENT ────────────────┤
│ ⊕  Planner          ●4   │   ← 4 briefs awaiting approval
│ ▤  Inventory             │
│ ⇄  Internal linking ●31  │   ← 31 suggested links
│ { }  Schema              │
├─ OUTPUT ─────────────────┤
│ ✉  Reports          ●1   │   ← 1 draft report to review
│ ✓  Action plan      ●10  │
│ ✧  AI Chat               │
├──────────────────────────┤
│ ⚙  Settings              │
│ ◐  Ollama: ready         │   ← live model status
└──────────────────────────┘
```

**Badge semantics — deliberately strict, because badge inflation kills the pattern:**

| Badge | Means |
|---|---|
| `●n` red | *n* items are **new since your last visit**, not *n* items total |
| `▲n` green | *n* positive changes worth knowing about |
| number | a current value (health score) |
| none | nothing changed |

A module with 400 long-standing issues and nothing new shows **no badge**. This is the
difference between a sidebar people scan and one they learn to ignore.

**Ollama status indicator** at the bottom is load-bearing: when the model isn't running, AI
features degrade and the user needs to know why without hunting.

---

## §11. Dashboard Layout

### Cross-client overview (`/`)

The agency home. One card per client, sorted by urgency, not alphabetically.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  All clients                              Last sync: 6 min ago  [Sync now] │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌── SUMMARY ─────────────────────────────────────────────────────────┐    │
│  │  15 clients · 18 sites                                             │    │
│  │  Clicks (28d)  142,308   ▲ 8.2%        Health avg   84   ▼ 2       │    │
│  │  New issues        27                  Reports due    3            │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  NEEDS ATTENTION                                                           │
│  ┌──────────────────────────┐  ┌──────────────────────────┐                │
│  │ ● Acme Corporation       │  │ ● Nova Systems           │                │
│  │   acme.com               │  │   novasystems.io         │                │
│  │                          │  │                          │                │
│  │   Health  71  ▼12        │  │   Health  88  ▬          │                │
│  │   Clicks  8,204  ▼4%     │  │   Clicks  3,110  ▼23%    │                │
│  │                          │  │                          │                │
│  │   ⚠ 14 new 404s in       │  │   ⚠ 3 queries lost       │                │
│  │     /blog/*              │  │     top-10 positions     │                │
│  │                          │  │                          │                │
│  │   [Open] [Ask AI]        │  │   [Open] [Ask AI]        │                │
│  └──────────────────────────┘  └──────────────────────────┘                │
│                                                                            │
│  HEALTHY                                                    [collapse ▾]   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐               │
│  │ Vertex     │ │ Blue Ridge │ │ Kalyan Ent │ │ Orbit Labs │               │
│  │ 94 ▲2      │ │ 91 ▬       │ │ 89 ▲1      │ │ 96 ▬       │               │
│  │ 12.4k ▲11% │ │ 4.2k ▲3%   │ │ 880 ▲7%    │ │ 22.1k ▲5%  │               │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘               │
└────────────────────────────────────────────────────────────────────────────┘
```

Healthy clients collapse to a compact strip. The screen's job is to direct attention, not
to display everything equally.

### Site dashboard (`/s/[site]`)

12-column grid, 4 rows. Every widget reads from a materialised view refreshed by the worker —
no widget triggers an external API call at render time, so the page loads in under 200 ms
regardless of how much history exists.

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Acme Corporation › acme.com          Last 28 days ▾        [Generate report]│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─ AI SUMMARY ──────────────────────────────────────────────────────┐     │
│  │ ✧ Clicks fell 4% while impressions rose 9% — you gained visibility │     │
│  │   on 41 new queries but average position slipped from 12.1 to      │     │
│  │   14.3. The drop is concentrated in /blog/, where 14 URLs began    │     │
│  │   returning 404 on 12 Nov after a category slug change.            │     │
│  │   [View the 14 URLs]  [Ask a follow-up]                            │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                                                            │
│  ┌── Clicks ────┐ ┌── Impress. ─┐ ┌── Avg pos ──┐ ┌── Conversions ──┐      │
│  │   8,204      │ │   142,891   │ │   14.3      │ │   87            │      │
│  │   ▼ 4.1%     │ │   ▲ 9.4%    │ │   ▼ 2.2     │ │   ▲ 12%         │      │
│  │  ╱╲╱‾╲╱╲__   │ │  __╱‾‾╲╱‾╲  │ │  ‾╲__╱‾╲_   │ │  _╱╲_╱‾╲╱‾      │      │
│  └──────────────┘ └─────────────┘ └─────────────┘ └─────────────────┘      │
│                                                                            │
│  ┌── PERFORMANCE OVER TIME ─────────────────┐ ┌── HEALTH ──────────┐       │
│  │                                          │ │       ╭───╮        │       │
│  │      clicks ─── impressions ┈┈┈          │ │      │ 71 │  ▼12   │       │
│  │   ┈┈┈┈┈┈╱╲┈┈┈┈╱‾‾╲┈┈┈┈┈┈╱‾╲┈┈           │ │       ╰───╯        │       │
│  │   ──╱╲──╱──╲──╱────╲───╱───╲─            │ │  Technical    62   │       │
│  │                                          │ │  Content      81   │       │
│  │  Oct 15        Nov 1        Nov 12       │ │  Performance  74   │       │
│  └──────────────────────────────────────────┘ │  Indexing     68   │       │
│                                               └────────────────────┘       │
│                                                                            │
│  ┌── TOP OPPORTUNITIES ─────────────────────┐ ┌── NEEDS ATTENTION ──┐      │
│  │ Query              Pos  Impr    CTR      │ │ ⛔ 14 new 404s      │      │
│  │ commercial fridge   11  4,201  0.4% ▸    │ │    /blog/*          │      │
│  │ walk-in cooler      14  2,880  0.3% ▸    │ │ ⚠ 6 pages missing   │      │
│  │ fridge repair cost   8  1,940  1.1% ▸    │ │    meta description │      │
│  │ commercial freezer  16  1,502  0.2% ▸    │ │ ⚠ LCP 4.1s on 8    │      │
│  │ [See all 47]                             │ │    templates        │      │
│  └──────────────────────────────────────────┘ └─────────────────────┘      │
│                                                                            │
│  ┌── RECENT CONTENT ────────────────────────┐ ┌── ACTIVITY ─────────┐      │
│  │ Post                   Pub    Clicks Pos │ │ ✓ Crawl  2h ago     │      │
│  │ Fridge maintenance…   3 Nov      142  18 │ │ ✓ GSC sync 6h ago   │      │
│  │ Choosing a walk-in…  21 Oct      380  11 │ │ ✓ Report generated  │      │
│  │ Energy costs guide…   8 Oct      910   7 │ │ ⏳ Lighthouse running│      │
│  └──────────────────────────────────────────┘ └─────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────┘
```

**Widget spec**

| Widget | Source table | Refresh | Load target |
|---|---|---|---|
| AI summary | `agent_runs` (cached narrative) | On sync completion | <50 ms (pre-generated) |
| KPI cards | `mv_site_kpis` | After each sync | <20 ms |
| Performance chart | `gsc_daily` | Nightly | <80 ms |
| Health gauge | `mv_site_health` | After crawl | <20 ms |
| Opportunities | `mv_query_opportunities` | Nightly | <40 ms |
| Needs attention | `issues` where `first_seen > last_visit` | Real-time | <30 ms |
| Recent content | `publications` ⋈ `gsc_daily` | Nightly | <50 ms |
| Activity | `jobs` | Real-time (SSE) | <20 ms |

**The AI summary is pre-generated, never on-demand.** A 9B model takes 10–20 seconds to write
that paragraph. Generating it when the worker finishes syncing and caching it means the
dashboard is instant. This is the single most important performance decision on this screen.

---

## §12. Every Page Wireframe

The 15 highest-value screens. Remaining screens follow the same shell.

### 12.1 Search Console (`/s/[site]/search-console`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Search Console          Last 28d ▾  vs previous ▾   Country ▾  Device ▾   │
├────────────────────────────────────────────────────────────────────────────┤
│  Clicks 8,204 ▼4.1%   Impr 142,891 ▲9.4%   CTR 5.7% ▼1.2   Pos 14.3 ▼2.2  │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │  [stacked area — clicks + impressions, 28d, hoverable]           │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                            │
│  [ Queries ] [ Pages ] [ Countries ] [ Devices ] [ Dates ]      [Export ⤓] │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ Query                    Clicks   Δ    Impr     CTR    Pos    Δ    │    │
│  │ ────────────────────────────────────────────────────────────────── │    │
│  │ commercial fridge repair  1,204  ▲8%  18,400   6.5%   4.2  ▲0.8   │    │
│  │ walk-in cooler price        880  ▼2%  14,220   6.2%   5.1  ▼0.3   │    │
│  │ commercial refrigeration    640  ▲21% 22,100   2.9%  11.4  ▲2.1   │    │
│  │ fridge maintenance cost      12  ▬     1,940   0.6%   8.0  ▬      │◀ ⚡ │
│  │ …                                                                  │    │
│  │                                              ⚡ = opportunity      │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  Rows 1–50 of 3,412                              [◀ Prev]  [Next ▶]        │
└────────────────────────────────────────────────────────────────────────────┘
```

Clicking a query expands it inline to show which pages rank for it and its 90-day position
history. The ⚡ marks rows meeting the opportunity rule (position 5–20, impressions above the
site median, CTR below the position-expected curve).

### 12.2 Technical Scanner (`/s/[site]/technical`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Technical Scanner        Crawl: 12 Nov 02:14 · 1,842 pages   [Crawl now]  │
├────────────────────────────────────────────────────────────────────────────┤
│  ● New this week (14)   All issues (312)   Resolved (28)   Ignored (7)     │
│                                              ▲ default tab is NEW          │
│  ┌── CRITICAL ──────────────────────────────────────────────────────┐      │
│  │ ⛔  404 Not Found                                    14 URLs  NEW │      │
│  │     All under /blog/ — appeared 12 Nov                            │      │
│  │     ✧ Cause: category slug changed from /blog/tips/ to /blog/     │      │
│  │       guides/ with no redirects. These 14 URLs still receive      │      │
│  │       1,240 impressions/mo between them.                          │      │
│  │     ✧ Fix: add 301 redirects old → new.                           │      │
│  │       [Download redirect map]  [View URLs]  [Ignore]              │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│  ┌── WARNING ───────────────────────────────────────────────────────┐      │
│  │ ⚠  Missing meta description                          6 URLs      │      │
│  │ ⚠  Title over 60 characters                         23 URLs      │      │
│  │ ⚠  Redirect chain longer than 2 hops                 4 URLs      │      │
│  └───────────────────────────────────────────────────────────────────┘      │
│  ┌── NOTICE ────────────────────────────────────────────────────────┐      │
│  │ ℹ  Images missing alt text                          88 URLs      │      │
│  │ ℹ  Pages with fewer than 300 words                  31 URLs      │      │
│  └───────────────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────┘
```

**The default tab is "New this week."** Opening on 312 issues trains the user to close the
tab; opening on 14 changes makes it the first thing checked every Monday (§7 Journey 2).

### 12.3 Keyword Clusters (`/s/[site]/keywords`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Keyword Clusters         3,412 queries → 47 clusters      [Re-cluster]    │
├────────────────────────────────────────────────────────────────────────────┤
│  Sort: Opportunity ▾    Intent: All ▾    Coverage: All ▾                    │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ ▸ Commercial refrigeration maintenance          Opportunity  87    │    │
│  │   11 queries · 4,201 impr/mo · avg pos 14.2 · CTR 0.6%             │    │
│  │   Intent: Commercial   Coverage: ✗ none                            │    │
│  │   [Generate brief]                                                 │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │ ▾ Walk-in cooler sizing                         Opportunity  74    │    │
│  │   8 queries · 2,880 impr/mo · avg pos 9.1 · CTR 1.8%               │    │
│  │   Intent: Informational   Coverage: ◐ partial (1 page)             │    │
│  │                                                                    │    │
│  │     walk in cooler size calculator    880 impr   pos 8   ▸         │    │
│  │     how big walk in cooler            640 impr   pos 11  ▸         │    │
│  │     walk in cooler dimensions         520 impr   pos 7   ▸         │    │
│  │     …                                                              │    │
│  │   Covered by: /guides/walk-in-cooler-guide  (pos 7)                │    │
│  │   [Improve existing page]  [Generate new brief]                    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.4 Content Planner (`/s/[site]/planner`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Content Planner                    November 2026 ▾     [Generate plan]    │
├────────────────────────────────────────────────────────────────────────────┤
│  [ Calendar ]  [ Backlog ]  [ In progress ]  [ Published ]                 │
│  ┌──────┬──────┬──────┬──────┬──────┬──────┬──────┐                        │
│  │ Mon  │ Tue  │ Wed  │ Thu  │ Fri  │ Sat  │ Sun  │                        │
│  ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤                        │
│  │  3   │  4   │  5   │  6   │  7   │  8   │  9   │                        │
│  │ ▣    │      │ ▣    │      │      │      │      │                        │
│  │ Comm │      │ Walk │      │      │      │      │                        │
│  │ frid │      │ -in  │      │      │      │      │                        │
│  │ Rahul│      │ Rahul│      │      │      │      │                        │
│  ├──────┼──────┼──────┼──────┼──────┼──────┼──────┤                        │
│  │ 10   │ 11   │ 12   │ 13   │ 14   │ 15   │ 16   │                        │
│  │      │ ▣    │      │ ▣    │      │      │      │                        │
│  │      │ Energ│      │ Fridg│      │      │      │                        │
│  └──────┴──────┴──────┴──────┴──────┴──────┴──────┘                        │
│                                                                            │
│  ▣ Brief ready   ▤ Draft   ▥ In review   ▦ Published                       │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.5 Brief Builder (`/s/[site]/content/brief/[id]`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Brief · Commercial refrigeration maintenance      Status: Draft  [Approve]│
├──────────────────────────────────────────┬─────────────────────────────────┤
│  TARGET QUERIES                          │  RESEARCH                       │
│  ┌────────────────────────────────────┐  │  Top 5 ranking pages analysed   │
│  │ commercial fridge maintenance      │  │  Avg word count      2,180      │
│  │   1,940 impr · pos 11              │  │  Avg headings           9       │
│  │ refrigeration servicing cost       │  │  Common schema     HowTo, FAQ   │
│  │     880 impr · pos 14              │  │                                 │
│  │ … 9 more                           │  │  ENTITIES TO COVER              │
│  └────────────────────────────────────┘  │  ✓ compressor    ✓ condenser    │
│                                          │  ✓ refrigerant   ✗ evaporator   │
│  OUTLINE                       [regen]   │  ✗ HACCP         ✗ defrost cycle │
│  ┌────────────────────────────────────┐  │                                 │
│  │ H1 Commercial Refrigeration…       │  │  INTERNAL LINKS (6)             │
│  │ ├ H2 Why maintenance matters   ⋮⋮  │  │  → /walk-in-cooler-guide        │
│  │ ├ H2 Monthly checklist         ⋮⋮  │  │  → /services/repair             │
│  │ ├ H2 Quarterly servicing       ⋮⋮  │  │  → /blog/energy-costs           │
│  │ ├ H2 What it costs             ⋮⋮  │  │  … 3 more                       │
│  │ ├ H2 DIY vs professional       ⋮⋮  │  │                                 │
│  │ ├ H2 Choosing a contractor     ⋮⋮  │  │  BRAND VOICE                    │
│  │ └ H2 FAQ                       ⋮⋮  │  │  Practical, no jargon, second   │
│  │ [+ Add section]                    │  │  person, UK spelling, avoid     │
│  └────────────────────────────────────┘  │  superlatives. [edit]           │
│  ⋮⋮ = drag to reorder                    │                                 │
│                                          │  Target: 1,800–2,200 words      │
└──────────────────────────────────────────┴─────────────────────────────────┘
```

### 12.6 Draft Editor (`/s/[site]/content/draft/[id]`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Draft · Commercial Refrigeration Maintenance     Saved 12s ago  [Publish ▾]│
├───────────────────────────────────────────┬────────────────────────────────┤
│  ┌─────────────────────────────────────┐  │  COVERAGE                      │
│  │ # Commercial Refrigeration          │  │  Queries      9/11  ▓▓▓▓▓▓▓░░  │
│  │   Maintenance: A Practical Guide    │  │  Entities     5/6   ▓▓▓▓▓▓▓▓░  │
│  │                                     │  │  Int. links   4/6   ▓▓▓▓▓▓░░░  │
│  │ If your walk-in cooler fails on a   │  │  Words     1,940 / 1,800–2,200 │
│  │ Friday night, you are not just      │  │  Readability  Grade 9  ✓       │
│  │ losing stock — you are losing the   │  │                                │
│  │ weekend's trade. Regular…           │  │  MISSING                       │
│  │                                     │  │  ✗ query: "fridge service      │
│  │ ## Why maintenance matters          │  │      interval" (620 impr)      │
│  │                                     │  │  ✗ entity: evaporator          │
│  │ …                                   │  │  ✗ 2 internal links unplaced   │
│  └─────────────────────────────────────┘  │                                │
│  [B] [I] [H2] [H3] [link] [list] [✧ AI]   │  ✧ AI ACTIONS                  │
│                                           │  [Rewrite section]             │
│                                           │  [Expand]  [Tighten]           │
│                                           │  [Match brand voice]           │
│                                           │  [Generate schema]             │
│                                           │  [Fact-check vs sources]       │
└───────────────────────────────────────────┴────────────────────────────────┘
```

### 12.7 AI Chat (`/s/[site]/chat`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  AI Assistant · acme.com                              Qwen 3.5 9B · local  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                      Why did clicks drop on the blog last month?  ◀ you    │
│                                                                            │
│  ✧  Blog clicks fell from 2,840 to 2,180 (−23%) between October and        │
│     November. Three things happened, in order of impact:                   │
│                                                                            │
│     1. On 12 Nov, 14 URLs under /blog/tips/ began returning 404 after      │
│        a category slug change. Those URLs had 1,240 impressions in         │
│        October. [crawl · 12 Nov] [affected URLs]                           │
│                                                                            │
│     2. "commercial refrigeration" slipped from position 8.2 to 11.4,       │
│        which typically costs roughly two-thirds of clicks at that          │
│        range. [GSC · query detail]                                         │
│                                                                            │
│     3. Impressions actually rose 9%, so this is a ranking and              │
│        availability problem, not a demand problem.                         │
│                                                                            │
│     Fixing the 404s is the highest-value action — the redirect map is      │
│     ready. [Open technical scanner]                                        │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │ Ask about this site…                                        [↑]  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│  Suggested: "What should I publish next?" · "Which pages are closest       │
│  to page 1?" · "Summarise this month for the client"                       │
└────────────────────────────────────────────────────────────────────────────┘
```

Every factual claim carries a bracketed citation linking to the rows that produced it. This
is a hard requirement (§7 Journey 4) — it is what makes an AI answer safe to repeat to a
client.

### 12.8 Internal Linking (`/s/[site]/linking`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Internal Linking            31 suggestions · 12 orphan pages  [Recompute] │
├────────────────────────────────────────────────────────────────────────────┤
│  [ Suggestions ]  [ Orphan pages ]  [ Link graph ]                         │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ From                    → To                   Rel.  Anchor        │    │
│  │ ────────────────────────────────────────────────────────────────── │    │
│  │ /blog/energy-costs      → /walk-in-guide       0.89  "walk-in      │    │
│  │                                                       cooler sizing"│    │
│  │   Place in ¶4: "…depends on how the unit is sized…"      [Apply]   │    │
│  │ ────────────────────────────────────────────────────────────────── │    │
│  │ /services/repair        → /blog/maintenance    0.86  "routine      │    │
│  │                                                       maintenance"  │    │
│  │   Place in ¶2: "…most callouts are preventable…"        [Apply]    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  [Apply all above 0.85]                                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.9 Reports (`/s/[site]/reports`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Reports                                              [Generate report ▾]  │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ November 2026 · Monthly          Draft — needs review              │    │
│  │ Generated 1 Dec 03:04                     [Review]  [Preview PDF]  │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │ October 2026 · Monthly           Sent 2 Nov · viewed 4×            │    │
│  │                                  [View]  [PDF]  [Share link]       │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │ Week 45 · Weekly (internal)      Generated 10 Nov                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.10 Action Plan (`/action-plan`, cross-client)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Action Plan · this week            All clients ▾    Assignee: All ▾       │
├────────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ #  Action                          Client   Impact  Effort  Owner  │    │
│  │ ── ──────────────────────────────  ──────   ──────  ──────  ─────  │    │
│  │ 1  Redirect 14 broken /blog/ URLs  Acme     ●●●●●   30 min  Dev  ▸ │    │
│  │ 2  Publish "commercial fridge…"    Acme     ●●●●○   4 hrs   Rahul▸ │    │
│  │ 3  Fix LCP on product template     Nova     ●●●●○   2 hrs   Dev  ▸ │    │
│  │ 4  Add meta desc to 6 pages        Acme     ●●○○○   20 min  Priya▸ │    │
│  │ 5  Apply 12 internal links         Vertex   ●●●○○   15 min  Priya▸ │    │
│  │ …                                                                  │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│  Est. total effort: 11.5 hrs · Est. impact: +2,400 clicks/mo               │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.11 Website Health (`/s/[site]/health`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Website Health                                   Last audit: 12 Nov 02:40 │
├────────────────────────────────────────────────────────────────────────────┤
│            ╭─────────╮                                                     │
│           │    71     │  ▼ 12 from last week                               │
│            ╰─────────╯                                                     │
│                                                                            │
│  Technical    62  ▓▓▓▓▓▓░░░░   ▼18   14 new 404s dominate this score       │
│  Content      81  ▓▓▓▓▓▓▓▓░░   ▬                                           │
│  Performance  74  ▓▓▓▓▓▓▓░░░   ▼3    LCP regressed on 8 templates          │
│  Indexing     68  ▓▓▓▓▓▓▓░░░   ▼9    31 pages dropped from the index       │
│                                                                            │
│  ┌── SCORE OVER TIME (90 days) ─────────────────────────────────────┐      │
│  │  100 ┤                                                           │      │
│  │   80 ┤  ─────╲___╱‾‾‾‾╲______                                    │      │
│  │   60 ┤                        ╲___                               │      │
│  │   40 ┤                                                           │      │
│  │      └─────────────────────────────────────                      │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────────────────┘
```

### 12.12 Competitors (`/s/[site]/competitors`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Competitors                                            [+ Add competitor] │
├────────────────────────────────────────────────────────────────────────────┤
│  ℹ  Competitor data here comes from crawling their public site. Ranking    │
│     keywords and backlink profiles require a paid data source — see        │
│     Settings › SERP provider.                                              │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ coldchain.co.uk                     Crawled 11 Nov · 640 pages     │    │
│  │ ────────────────────────────────────────────────────────────────── │    │
│  │ Content themes    maintenance (31) · installation (24) · parts(18) │    │
│  │ Publishing        ~6 posts/month                                    │    │
│  │ Avg word count    2,410  (yours: 1,680)                            │    │
│  │ Schema            Article, FAQ, LocalBusiness  (you: Article only) │    │
│  │ Topics you lack   HACCP compliance · defrost cycles · energy audits│    │
│  │                                                     [View gap ▸]   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

The disclosure banner is deliberate. It is better to state the limitation on the screen than
to let a user assume the competitor data is complete.

### 12.13 Settings › AI providers (`/settings/ai`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Settings › AI                                                             │
├────────────────────────────────────────────────────────────────────────────┤
│  LANGUAGE MODEL                                                            │
│  ● Local (Ollama)                                            $0 · default  │
│      Model      qwen3.5:9b ▾          Status  ● ready                      │
│      Embedding  nomic-embed-text ▾    Status  ● ready                      │
│      Reasoning  ○ off (recommended)  ● on                                  │
│         Off is ~30× faster for structured tasks. Schema-constrained         │
│         output makes chain-of-thought redundant here.                      │
│                                                                            │
│  ○ Remote (bring your own key)                            billed to you    │
│      Provider   [ Anthropic ▾ ]                                            │
│      API key    [ ················ ]                        [Test]         │
│      Used for   ☑ Long-form drafts  ☐ Everything else                      │
│         Only the tasks you tick are sent remotely. Everything else          │
│         stays local.                                                       │
│                                                                            │
│  SERP DATA                                                                 │
│  ● Local scraper                                    $0 · ~200 queries/day  │
│  ○ Apify                                                   billed to you   │
│      API token  [ ················ ]                        [Test]         │
│      Budget cap [ 5,000 ] results/month — hard stop when reached           │
└────────────────────────────────────────────────────────────────────────────┘
```

Both adapter types share one screen and one mental model — local by default, remote by
explicit opt-in, with the cost consequence stated inline. See §17 and §24.

### 12.14 Client portal (`/portal/[token]`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [Agency logo]                                Acme Corporation · acme.com │
├────────────────────────────────────────────────────────────────────────────┤
│  Your SEO performance                            Last 28 days ▾            │
│                                                                            │
│  ┌── Clicks ────┐ ┌── Impress. ─┐ ┌── Conversions ┐ ┌── Health ──┐         │
│  │   8,204      │ │   142,891   │ │      87       │ │     71     │         │
│  │   ▼ 4.1%     │ │   ▲ 9.4%    │ │    ▲ 12%      │ │            │         │
│  └──────────────┘ └─────────────┘ └───────────────┘ └────────────┘         │
│                                                                            │
│  ┌── PERFORMANCE ───────────────────────────────────────────────────┐      │
│  │  [chart]                                                         │      │
│  └──────────────────────────────────────────────────────────────────┘      │
│                                                                            │
│  RECENT REPORTS                        PUBLISHED THIS MONTH                │
│  ▸ November 2026   [PDF]               ▸ Commercial Refrigeration…  3 Nov  │
│  ▸ October 2026    [PDF]               ▸ Walk-in Cooler Sizing     21 Oct  │
└────────────────────────────────────────────────────────────────────────────┘
```

No tool branding, no navigation to anything else, no other client reachable. Enforced by RLS,
not just by hiding links (§28).

### 12.15 Onboarding wizard (`/onboarding`)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                     ●───────●───────○───────○                              │
│                  Organization  Google  Properties  Client                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│         Connect your Google account                                        │
│                                                                            │
│         We'll request read-only access to:                                 │
│                                                                            │
│         ⌕  Search Console      rankings, queries, links                    │
│         ▲  Analytics (GA4)     traffic and conversions                     │
│         ◈  Business Profile    local rankings (optional)                   │
│                                                                            │
│         Everything stays on this machine. We never send your               │
│         client data anywhere — the only outbound calls are to              │
│         Google's own APIs, using the access you grant here.                │
│                                                                            │
│                    [ Connect Google account ]                              │
│                                                                            │
│         Don't have Search Console access to your clients' sites?           │
│         That's required — here's how to request it.  [Read ▸]              │
└────────────────────────────────────────────────────────────────────────────┘
```

---

### Design system notes

| | |
|---|---|
| Framework | Next.js 15 App Router, React Server Components by default |
| Styling | Tailwind CSS |
| Components | shadcn/ui (Radix primitives — accessible, unstyled, copy-in not dependency) |
| Charts | Recharts |
| Tables | TanStack Table — virtualised; GSC query tables reach 50,000 rows |
| Icons | Lucide |
| Theme | Light and dark, following system preference |
| Density | Compact by default. This is a professional tool used for hours, not a marketing site |
| Data fetching | RSC for initial load; SSE for job progress and AI streaming |

**Accessibility floor:** keyboard navigable throughout, visible focus rings, 4.5:1 contrast
minimum, semantic table markup, no colour-only status encoding (every colour badge also
carries a glyph — `●`, `▲`, `⛔`, `⚠`, `ℹ`).

---

[← 03 User Journeys](03-user-journeys.md) · [Index](../README.md) · [Next: 05 — Database →](05-database.md)
