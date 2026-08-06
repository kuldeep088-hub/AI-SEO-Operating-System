# 01 — Product Vision

Sections §1–§4. [← Back to index](../README.md)

---

## §1. Product Vision

### One sentence

**An SEO operating system that runs entirely on your own machine, turns Google's free data
into agency-grade deliverables using a local AI model, and costs nothing to operate at any
number of clients.**

### The longer version

Every SEO agency runs the same loop: pull data from four or five tools, notice what changed,
decide what to do about it, do it, then explain it to the client. The tools handle the first
step. A human does the other four.

That is backwards. Pulling data is the part software is best at, and it is the part agencies
pay the most for — $500 to $1,500 per month for Ahrefs, Semrush, Surfer, Screaming Frog, and
a reporting tool, none of which talk to each other. Meanwhile the actual work — deciding what
matters this week, writing the brief, drafting the post, explaining the drop in traffic to a
worried client — is done by hand in Google Docs and Slides.

This product inverts that. The data layer is commoditised and free. The synthesis layer is
where the AI goes.

### Why this can be free

The commercial SEO tool industry is built on one asset: a proprietary index of the web —
which pages exist, what they rank for, who links to whom. Ahrefs spends heavily to crawl the
web and keep that index fresh, and charges accordingly.

But an agency does not need an index of *the web*. It needs an index of **its clients'
sites** and a handful of competitors. And for its clients' own sites, that data already
exists, free, at higher accuracy than any third party can offer:

- **Google Search Console** reports every query a site ranked for, with position, impressions,
  clicks, and CTR, segmented by page, country, device, and date, for the last 16 months. It
  is measured from Google's own serving logs. Ahrefs estimates the same numbers from a
  sampled crawl. GSC is not a cheaper substitute — it is the source of truth that Ahrefs is
  approximating.
- **GSC's link report** lists the sites linking to your client. Free.
- **GA4** provides the sessions, conversions, and revenue that turn rankings into a business
  outcome. Free.
- **Lighthouse**, run locally, gives unlimited Core Web Vitals and performance audits with no
  API quota at all.
- **Your own crawler** produces everything Screaming Frog produces — status codes, redirect
  chains, canonicals, hreflang, thin content, orphan pages, internal link graphs.

What remains genuinely proprietary is information about *other people's* websites: what a
competitor ranks for, and who links to them. That is a real gap and this document does not
pretend otherwise (see §2 and §56). It is also, for most agency work, the least load-bearing
data in the stack.

### Why the AI can be local

The tasks an SEO platform actually asks of a language model are mostly **structured**:
cluster 4,000 queries into topics, classify search intent, extract entities from a page,
generate valid JSON-LD, pick which 12 internal links to add, summarise what changed this
week, write a brief. These are constrained-output tasks where a well-prompted 9B model with
schema-enforced decoding performs close to a frontier model, at zero marginal cost and with
no data leaving the machine.

The one task where the gap is real is long-form prose — a publishable 2,000-word article in
one pass. §17 and §39 address that directly with chunked, outline-driven generation, and with
an opt-in provider adapter for the occasional deliverable that warrants more.

### The design principles

1. **Free by default, paid by exception.** Nothing in the default path costs money. Paid
   services (a SERP vendor, a frontier LLM) exist only as adapters behind an interface, off
   unless explicitly switched on.
2. **Local by default.** The database, the model, the crawler, and the app all run on one
   machine. No data leaves it except the API calls to Google that the user authorised.
3. **Measured over estimated.** Where Google reports a number directly, use it. Never show an
   estimate next to a measurement without labelling which is which.
4. **The deliverable is the product.** An agency's output is a report, a brief, a fixed page,
   a published post. Features that do not end in one of those are decoration.
5. **One machine, many clients.** Multi-client is not a "team plan" — it is the primary use
   case from the first schema migration.

### What this is not

- Not a SaaS product. It runs on your Mac. (§51 covers what would change if that ever shifted.)
- Not a rank tracker with an SEO dashboard bolted on. Ranking data is an input, not the point.
- Not a content mill. The blog generator is one module of 28, and it is deliberately
  outline-driven rather than one-shot.
- Not a replacement for an SEO's judgment. It is a replacement for an SEO's *data-gathering
  and reporting time*, which is where most of the hours go.

---

## §2. Problems this product solves

### Problem 1 — The tool stack costs more than it returns

A three-person agency managing fifteen clients typically pays:

| Tool | Purpose | Typical cost/mo |
|---|---|---|
| Ahrefs or Semrush | Rankings, backlinks, competitor research | $199–499 |
| Surfer or Clearscope | Content optimisation | $89–199 |
| Screaming Frog | Technical crawling | $259/yr (~$22) |
| AgencyAnalytics or similar | Client reporting | $60–180 |
| An AI writing tool | Drafts | $49–99 |
| **Total** | | **$420–1,000** |

At fifteen clients that is $28–66 per client per month in tooling before anyone does any
work. For a small agency it is often the second-largest line item after salaries.

**What this solves it with:** the same capabilities from free Google APIs, a local crawler,
and a local model. The cost line goes to zero and stays there regardless of client count —
which also removes the perverse incentive to under-serve small accounts because the tooling
overhead makes them unprofitable.

### Problem 2 — The data lives in five places and the synthesis lives in a human head

Rankings are in Ahrefs. Traffic is in GA4. Impressions are in GSC. Technical issues are in a
Screaming Frog export. Page speed is in PageSpeed Insights. Content scores are in Surfer.

Nothing joins them. So when a client asks "why did traffic drop last month?", answering it
means opening five tabs, exporting three CSVs, and reasoning across them manually. That
question gets asked by every client every month, and it takes 30–90 minutes to answer
properly each time.

**What this solves it with:** one Postgres database where GSC queries, GA4 sessions, crawl
results, Lighthouse scores, and rank history are joined on `site_id` and `date`. The AI Chat
Assistant (§5, module 21) answers that question against the joined data in seconds, with the
underlying numbers cited so the SEO can verify before repeating it to the client.

### Problem 3 — Reporting is unpaid labour

Client reports are the single largest recurring time cost in an agency and they generate zero
new value — the work already happened; the report just describes it. A monthly report for one
client is 60–120 minutes of exporting, charting, and writing narrative. At fifteen clients
that is 15–30 hours a month, every month, permanently.

**What this solves it with:** the Weekly and Monthly Report Generators (§5, modules 19–20)
assemble the data automatically and use the local model to write the narrative — what
changed, why it probably changed, what was done about it, what happens next. The SEO reviews
and edits rather than composes. Target: 90 minutes down to 10.

### Problem 4 — Technical audits go stale the day they are delivered

A technical audit is usually a one-off PDF. The site changes the following week — a developer
ships a release, a plugin updates, a redirect breaks — and nobody notices until the next
quarterly audit.

**What this solves it with:** the crawler runs weekly on a schedule (§24), diffs against the
previous crawl, and only surfaces *what changed*. A new 404, a canonical that flipped, a
page that dropped out of the index. Continuous monitoring instead of periodic archaeology.

### Problem 5 — Keyword research produces spreadsheets, not plans

Standard keyword research output is a 3,000-row spreadsheet with volume and difficulty
columns. Turning that into a content calendar — grouping into topics, deciding what to write
first, writing the brief — is still entirely manual.

**What this solves it with:** GSC queries (already free, already specific to the client) are
embedded and clustered locally (§6, §20), labelled into topics by the model, scored by
opportunity (high impressions × low CTR × position 5–20 is the classic quick win), and
turned into a prioritised content plan with briefs. The spreadsheet step disappears.

### Problem 6 — AI content tools produce content that reads like AI content

One-shot "write me a 2,000-word article on X" produces generic, structurally identical prose
regardless of which model generates it. It needs heavy editing, which erases the time saving.

**What this solves it with:** a deliberately multi-stage pipeline (§17) — research from the
client's *own* GSC data and crawled competitor content, a structured brief, an outline
approved by a human, then section-by-section generation against that outline, then an
editing pass with the client's brand voice from memory (§22). Slower and better, rather than
instant and unusable.

### Problem 7 — Client data goes to third parties

Every SaaS SEO tool means client GSC data, analytics, and content sit on someone else's
servers. For clients in regulated sectors, or with strict procurement, that is a real
objection and sometimes a blocker.

**What this solves it with:** everything runs locally. The only outbound calls are to
Google's own APIs, using OAuth grants the client explicitly authorised. No client data
touches a third-party SaaS. This is a genuine competitive advantage in pitches, not just a
cost saving.

### What this deliberately does not solve

Stated up front so nobody discovers it in month three:

| Not solved | Why |
|---|---|
| "What keywords does my competitor rank for?" | Requires a proprietary keyword-ranking index. No free source exists. |
| "Who links to my competitor?" | Requires a proprietary link index. GSC covers your own sites only. |
| Frontier-quality long-form prose in one pass | A 9B local model is genuinely weaker here. Mitigated by pipeline design (§17), not eliminated. |
| Tracking rankings for sites you don't own in GSC | Needs SERP scraping, which caps around 200/day locally. |

Full treatment in §38 and §56.

---

## §3. Target Users

The product is built first for **Growleads Agency** and generalises outward. Ranked by fit:

### Primary — SEO and digital marketing agencies (2–20 people)

The core user. Manages 5–50 client sites, has GSC and GA4 access to all of them, produces
monthly reports, and feels tool costs directly on the P&L. Multi-client management, white-
label reporting, and role-based access exist for this user.

**Why this fits:** the free-data argument is strongest when you have authorised access to
your clients' Search Console. That is exactly an agency's position and nobody else's.

### Primary — Freelance SEO consultants

Same shape as an agency, smaller. Often the most price-sensitive user — a $400/month tool
stack against a $3,000/month revenue is a serious drag. Runs 3–10 clients from one laptop.

**Why this fits:** the entire product runs on the laptop they already own. Zero marginal
cost per additional client is decisive at this scale.

### Secondary — In-house growth teams at SaaS companies

One site, deep. Cares less about multi-client and more about content velocity, technical
health, and tying rankings to pipeline via GA4. Uses the content planner and blog generator
heavily.

**Why this fits partially:** they have full GSC/GA4 access to their own property, so the
data story works. They typically care more about competitor intelligence than an agency
does, which is the weakest part of the free build.

### Secondary — Startup founders doing their own SEO

Pre-hire, running SEO themselves alongside everything else. Needs the Action Plan Generator
more than the analytics — "tell me the three things to do this week."

**Why this fits partially:** strong fit on cost and on the action-plan module; weak fit on
setup complexity. They are the least likely to run Docker comfortably. §7 addresses this
with a single `setup.sh`.

### Tertiary — Larger agencies (20+ people)

Would want hosted, multi-user, SSO, and audit trails. The schema supports it (§28) but the
local-only deployment does not. §51 covers what would change.

### Explicitly not the target

- **Enterprise SEO teams** — need vendor SLAs, procurement-approved suppliers, and SOC 2.
- **Affiliate and programmatic SEO at scale** — need bulk SERP data by the million, which is
  precisely what the free architecture cannot do.
- **Anyone without Search Console access to the sites they work on.** This is the hard
  qualifying question. Without GSC, roughly 60% of the product's value disappears.

---

## §4. User Personas

### Persona 1 — Anuj, Agency Owner

| | |
|---|---|
| **Role** | Founder, Growleads Agency |
| **Team** | 3–6 people |
| **Clients** | 12–20 sites, mixed sectors, mostly Indian SMB and SaaS |
| **Technical level** | High. Runs local LLMs, writes Python, comfortable with Docker |
| **Current stack** | Semrush, Screaming Frog, GSC, GA4, Google Sheets, Google Slides |
| **Current tooling cost** | ~$350/month |

**The job he hires this for:** *"Give my team back the 25 hours a month they spend building
reports and pulling exports, and delete the tool subscription line from my P&L."*

**Pains**
- Tool costs scale with client count but revenue per client does not
- Report week is a dead week — no client work ships
- Junior staff spend their first six months doing exports rather than learning SEO
- Client data sitting in US SaaS platforms is an objection in some pitches

**What success looks like:** monthly reporting drops from 20 hours to 3. Tool spend goes to
zero. He can profitably take a ₹25,000/month client because the marginal tooling cost is nil.

**Where he'll push back:** if the local model's writing needs more editing than it saves.
He'll measure this immediately and honestly.

---

### Persona 2 — Priya, SEO Strategist

| | |
|---|---|
| **Role** | Senior SEO at a 6-person agency |
| **Clients** | 8 sites she owns end-to-end |
| **Technical level** | Medium. Excel-fluent, no code, comfortable with any web UI |
| **Current stack** | Ahrefs, Surfer, GSC, GA4, Notion |

**The job she hires this for:** *"Tell me what changed on my sites this week and what I
should do about it, without me having to go looking."*

**Pains**
- Discovers technical breakages weeks late, usually because the client noticed first
- Keyword research produces spreadsheets she then has to turn into a plan by hand
- Writing briefs is 45 minutes each and she writes six a month
- Can't remember which of eight clients has which brand voice rules

**What success looks like:** opens the dashboard Monday, sees a ranked list of what changed
across all eight sites, and spends the morning fixing rather than finding.

**Where she'll push back:** she will not use anything that requires the terminal. Every
workflow she touches must be in the browser.

---

### Persona 3 — Rahul, Content Writer

| | |
|---|---|
| **Role** | In-house writer, works across the agency's clients |
| **Technical level** | Low. Google Docs and a CMS |
| **Current stack** | Google Docs, Surfer, ChatGPT, WordPress |

**The job he hires this for:** *"Give me a brief that already knows what the client sounds
like and what the page needs to cover, so I'm editing instead of starting from nothing."*

**Pains**
- Briefs arrive as a keyword and a word count
- Has to re-learn each client's tone every time he switches
- Generic AI drafts take longer to fix than to rewrite
- Never knows whether a published post actually worked

**What success looks like:** opens a brief that contains the outline, the entities to cover,
the internal links to include, and the brand voice rules — then edits a draft rather than
writing from scratch. Sees the post's GSC performance 30 days later in the same tool.

**Where he'll push back:** if the draft quality is bad enough that rewriting is faster, he
will quietly stop using it and go back to ChatGPT. §17's pipeline design exists because of
this persona.

---

### Persona 4 — Sneha, Freelance SEO Consultant

| | |
|---|---|
| **Role** | Solo, 5 retainer clients |
| **Revenue** | ~₹2.5L/month |
| **Technical level** | Medium-high. Will run a script if there are instructions |
| **Current stack** | Ahrefs Lite, GSC, GA4, Looker Studio |
| **Current tooling cost** | ~$120/month (~7% of revenue) |

**The job she hires this for:** *"Look like a ten-person agency without a ten-person agency's
tool budget."*

**Pains**
- Tooling is a meaningful percentage of revenue
- Reporting eats her billable Fridays
- Can't take small clients profitably
- Competes against agencies with better-looking deliverables

**What success looks like:** white-labelled monthly reports that look like an agency
produced them, generated in minutes, at zero cost, so a ₹20,000/month client is profitable.

**Where she'll push back:** setup friction. If `setup.sh` fails on her machine she has no one
to ask. §7 and §32 treat first-run reliability as a feature, not a nicety.

---

### Persona 5 — Vikram, SaaS Growth Lead

| | |
|---|---|
| **Role** | Head of Growth, 30-person B2B SaaS |
| **Sites** | One, ~800 pages, plus a docs subdomain |
| **Technical level** | High. Ships code |
| **Current stack** | Ahrefs, GSC, GA4, Amplitude, a headless CMS |

**The job he hires this for:** *"Connect what we rank for to what actually generates
pipeline, and tell me which pages to write next."*

**Pains**
- Rankings and revenue live in different tools and nobody joins them
- Content velocity is capped by brief-writing, not writing
- Technical debt accumulates silently across releases
- Needs to justify SEO spend in pipeline terms to a CFO

**What success looks like:** a dashboard that shows GSC positions joined to GA4 conversions
by landing page, and a content plan ranked by estimated pipeline rather than search volume.

**Where he'll push back:** he wants competitor intelligence — what are our three competitors
ranking for that we aren't. This is the weakest part of the free build, and §38 says so
plainly rather than overselling the topical-gap substitute.

---

### What the personas have in common

Every one of them has **authorised Search Console access to the sites they work on**. That
is the single qualifying condition for this product, and it is what makes the free data
architecture viable. Anyone without it should use a commercial tool instead — this document
would be doing them a disservice to suggest otherwise.

---

[← Back to index](../README.md) · [Next: 02 — Features →](02-features.md)
