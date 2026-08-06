# 13 — Business & Strategy

Sections §50–§57. [← Back to index](../README.md)

---

## §50. Future AI Features

Ordered by value-to-effort, with the honest constraint noted for each.

### Near-term — buildable on the current architecture

**1. Anomaly narration.** Instead of the user asking "why did traffic drop?", the system
detects the anomaly and explains it unprompted. All the inputs already exist — GSC time series,
crawl diffs, Lighthouse history. Needs statistical detection (seasonal decomposition, not a
naive threshold) plus a narration pass. **The highest-value unbuilt feature**, because it moves
the product from answering questions to raising them.

**2. Cannibalisation detection.** Two pages competing for the same query is common and
invisible without joining data. `gsc_daily` already has query→page mapping; detection is a
`GROUP BY query HAVING count(DISTINCT page) > 1` with a position-volatility filter. A day of
work, and it finds real problems on almost every site.

**3. Content decay prediction.** Regression over each page's 16-month GSC trajectory to flag
posts sliding before they fall off page one. Refreshing decaying content is the highest-ROI
content work in SEO and almost nobody does it systematically.

**4. Automated brief-from-a-competitor-page.** Point it at a URL, get a brief that covers what
that page covers plus what it misses. The crawler and entity modules already do the work.

**5. Report memory.** "Last quarter we said X would happen — here's what did." Requires only
embedding past narratives (already planned, §19) and retrieving them at generation time. Makes
reports feel like a continuing relationship rather than a monthly data dump.

### Medium-term — needs new capability

**6. Multi-step autonomous action.** "Fix all missing meta descriptions" → generate, review,
push via WordPress. The pieces exist; what's missing is a review-and-approve queue for bulk AI
changes. The interesting design problem is the approval UX, not the AI.

**7. Voice-of-customer mining.** GSC queries are literal customer language. Clustering them by
emotional register and problem framing — not just topic — produces messaging insight, not
just SEO insight. Genuinely differentiated, and free.

**8. Predictive opportunity scoring.** Current scoring is a formula (§43). With 12+ months of
outcome data, a small model trained on "which opportunities we acted on and what happened"
would beat the heuristic. Needs data this system doesn't have yet — revisit in year two.

**9. Cross-client benchmarking.** "Your 4.2% CTR at position 6 is below the 6.1% median across
similar sites." Requires care: aggregate only within one agency's own clients, never across
installations, and never in a way that could identify a client.

### Long-term — constrained by the $0 architecture

**10. Automated technical fixes via PR.** Generate a redirect map, open a pull request against
the client's repo. Feasible; needs Git integration and a lot of trust.

**11. Multimodal page analysis.** Screenshot a page and have a vision model assess layout,
above-the-fold content, and CLS causes. **Blocked at $0** — a vision model that fits alongside
Qwen 3.5 in 16 GB is not currently good enough. Revisit as local vision models improve.

**12. Real-time SERP monitoring.** Requires SERP volume the free path can't supply (§38).
Available only with the Apify adapter.

### Deliberately not on this list

- **Autonomous publishing without review.** The product's credibility depends on a human
  approving anything a client sees. Removing the gate would be a feature that destroys trust.
- **AI-generated link building outreach.** Spam with extra steps.
- **"AI SEO score" as a headline metric.** A number that correlates with nothing is worse than
  no number. The health score (§43) is explicitly decomposed into its parts for this reason.

---

## §51. Business Model

### The model is not SaaS

This is a **capability investment for an agency**, not a product to sell. The return shows up
in the agency's P&L in four places:

| Lever | Mechanism | Estimated annual value |
|---|---|---|
| Tool cost eliminated | $419–999/mo of subscriptions removed | **$5,000–12,000** |
| Reporting time recovered | 20 h/mo → 3 h/mo at 15 clients, valued at ₹1,500/h | **~₹3.1L (~$3,700)** |
| Smaller clients become profitable | Zero marginal tooling cost per client | Varies — potentially the largest |
| Differentiated pitch | "Your data never leaves our machine" + live client dashboard | Win-rate effect |

The third is the one that compounds. When tooling costs $30/client/month, a ₹20,000/month
client is marginal. When it costs nothing, that client is profitable — which opens a segment
most agencies decline.

### Why not sell it

The obvious question, answered honestly:

| Reason | Detail |
|---|---|
| **The AI doesn't multi-tenant** | Local inference means a GPU per concurrent stream. §40: ~$200–400/mo before a single customer |
| **Support becomes the product** | Fifteen agencies with fifteen Google Cloud project configurations is a support desk, not a side project |
| **The moat is the insight, not the code** | The free-data thesis (§1) is the valuable part, and publishing it as content (§44) may be worth more than selling the software |
| **Competitive disclosure** | Selling it hands the approach to competing agencies |

### The three paths, if productisation ever tempts

**Path A — Open source it.** Publish the repo, keep running it internally. Costs nothing,
builds the agency's technical reputation, generates inbound. The `RemoteProvider` and
`ApifyProvider` adapters mean others can scale it their own way. **The most likely good
outcome**, and the one §44's content strategy naturally leads toward.

**Path B — Hosted SaaS with BYO API key.** Host the app; each customer supplies their own LLM
key. Infrastructure drops from ~$400/mo to ~$100/mo because the expensive part moves to the
customer. Viable, but it makes support the business.

**Path C — Productised service.** Don't sell software; sell the outcome. "Full SEO management,
₹X/month" — where the tool is why the margin works. **This is the highest-margin path** and
requires building nothing further.

**Recommendation: build for internal use, publish the thinking (Path A's content half), and
let Path C be where the money comes from.** Revisit hosting only if inbound demand for the
software itself becomes loud, which it probably won't and doesn't need to.

---

## §52. SaaS Pricing

*Hypothetical — pricing if Path B were ever pursued. Not a plan.*

### The constraint that shapes any pricing

Whoever pays for inference determines whether the economics work:

| Model | Cost to you | Viable? |
|---|---|---|
| Host GPU, unlimited AI | $200–400/mo fixed + growth | ❌ Requires ~$2k MRR before profit |
| Host GPU, metered credits | Same fixed cost, revenue scales | ⚠️ Works at scale, brutal early |
| **BYO API key** | ~$100/mo total | ✅ **AI cost is structurally zero to you** |

**BYO key is the only structurally sound option for a small operator.** It also happens to be
honest: the customer sees exactly what their AI usage costs, and can choose local Ollama
instead and pay nothing.

### Illustrative tiers

| | Solo | Agency | Agency+ |
|---|---|---|---|
| **Price** | $29/mo | $99/mo | $249/mo |
| Client sites | 3 | 15 | 50 |
| Users | 1 | 5 | 20 |
| Crawl frequency | Weekly | Weekly | Daily |
| Client portals | 1 | Unlimited | Unlimited, white-label |
| AI | BYO key | BYO key | BYO key |
| SERP data | — | BYO Apify | BYO Apify |
| Support | Community | Email | Priority |

### Unit economics at the Agency tier

```
Revenue per org                    $99.00
  ─ Infrastructure (amortised)     $ 4.50    app server + Postgres ÷ ~40 orgs
  ─ Storage                        $ 1.20
  ─ Email                          $ 0.50
  ─ Payment processing (2.9%+30¢)  $ 3.17
  ─ Support (0.5 h @ $40)          $20.00    ← the real cost
  ────────────────────────────────────────
  Gross margin                     $69.63    (70%)
```

**Support is the dominant cost and the reason to hesitate.** At 0.5 hours per org per month
it's 70% margin; at 2 hours it's negative. Google Cloud project setup, OAuth consent screens,
and property permissions are all confusing, and every one of them generates a ticket.

**Break-even: ~35 paying orgs** against a founder's part-time attention. Reaching 35 paying
agencies is a real go-to-market effort — which is the honest reason §51 recommends against it.

---

## §53. Enterprise Features

*What a larger organisation would require. None are built; several are cheap because the
schema anticipated them.*

| Feature | Effort | Notes |
|---|---|---|
| SSO / SAML | Medium | Auth is already provider-agnostic (§16) |
| SCIM provisioning | Medium | `memberships` supports it structurally |
| Audit log export | **Low** | `audit_log` exists; needs an export endpoint |
| Custom roles | Medium | Currently five fixed roles; would need a permission matrix |
| IP allowlisting | Low | Middleware |
| Data residency | High | Fundamentally at odds with local-first |
| SLA / uptime guarantee | High | Requires hosting, on-call, redundancy |
| SOC 2 | Very high | 6–12 months, $30k+ — a business decision, not a technical one |
| Sandbox environment | Medium | A second Compose stack |
| Bulk API | Low | Endpoints exist; needs higher rate limits and pagination cursors |
| Private LLM endpoint | **Low** | `RemoteProvider` already abstracts this — point it at their Azure/Bedrock deployment |

**The two that are nearly free** are audit log export and private LLM endpoints, both because
the architecture already anticipated them. Everything else is real work, and SOC 2 is a
different company.

---

## §54. Agency Features

*The features that exist because this was built by an agency for itself. These are the
product's actual differentiation.*

### Built into the plan

| Feature | Where | Why it matters |
|---|---|---|
| Multi-client from migration one | §13, §28 | Not a "team plan" bolted on later |
| Cross-client dashboard sorted by urgency | §11 | Priya's Monday, 8 clients, 15 minutes |
| Cross-client action plan | §12.10 | Prioritises across the whole book of business |
| White-label reports | §12.9 | Agency logo, client colours, zero tool branding |
| Live client portals | §12.14 | Retainer-defending, zero marginal cost |
| Per-client brand voice | §22 | Rahul stops re-learning eight tones |
| Client-scoped RBAC | §16, §28 | A client sees only their own data, enforced twice |
| Bulk operations | §5.24 | Crawl all, report all, one action |
| Staggered scheduling | §24 | 15 sites don't saturate one connection |

### Worth building next

**Client onboarding checklist.** A per-client template — GSC access requested, GA4 linked,
brand voice captured, competitors identified, first crawl clean. Agencies onboard constantly
and forget steps constantly.

**Deliverable calendar.** One view of what is due to whom and when across every client. This
is the thing agencies currently track in a spreadsheet.

**Time-to-value tracking.** Which actions were taken, and what happened 30/60/90 days later.
The single most powerful retention argument an agency can make at renewal, and the data
already exists in `publications` ⋈ `gsc_daily`.

**Proposal generator.** Run a prospect's site through the crawler and GSC (with access), and
produce a findings document. The pitch tool writes itself from modules that already exist.

### The agency insight most tools miss

Commercial SEO tools are built for **one site, deeply**. Agencies work **many sites, shallowly,
in rotation** — the question is never "everything about acme.com" but "which of my fifteen
clients needs me today, and why."

Every design choice in §10–§12 follows from that: diffs over state, badges that mean *new*
rather than *total*, urgency-sorted client cards, a cross-client action plan. It is why the
sidebar shows `●14` for fourteen *new* issues and nothing at all for four hundred
long-standing ones (§10).

---

## §55. Competitive Comparison

### Against the stack it replaces

| | This | Ahrefs | Semrush | Surfer | Screaming Frog | AgencyAnalytics |
|---|---|---|---|---|---|---|
| **Cost/mo** | **$0** | $199+ | $139+ | $89+ | ~$22 | $60+ |
| Own-site rankings | ✅ GSC (measured) | ◐ estimated | ◐ estimated | — | — | ◐ via GSC |
| Competitor rankings | ❌ | ✅ | ✅ | ◐ | — | — |
| Own backlinks | ✅ GSC | ✅ | ✅ | — | — | ◐ |
| Competitor backlinks | ❌ | ✅ | ✅ | — | — | — |
| Technical crawl | ✅ | ✅ | ✅ | — | ✅ | — |
| Core Web Vitals | ✅ unlimited | ◐ | ◐ | — | ◐ | ◐ |
| Keyword clustering | ✅ from GSC | ◐ | ✅ | ◐ | — | — |
| Content briefs | ✅ | — | ◐ | ✅ | — | — |
| AI content generation | ◐ local | — | ◐ | ✅ | — | — |
| Internal link suggestions | ✅ | ◐ | ◐ | ◐ | ◐ | — |
| Entity optimisation | ✅ | — | — | ◐ | — | — |
| GSC ⋈ GA4 join | ✅ | — | — | — | — | ◐ |
| Multi-client | ✅ | ◐ | ✅ | ◐ | — | ✅ |
| White-label reports | ✅ | — | ✅ | — | — | ✅ |
| Live client portal | ✅ | — | ◐ | — | — | ✅ |
| Conversational AI over your data | ✅ | — | ◐ | — | — | — |
| Data stays local | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Customisable | ✅ own code | ❌ | ❌ | ❌ | ◐ | ❌ |

✅ full · ◐ partial · ❌ none

### Where each competitor genuinely wins

Stated plainly, because a comparison table that shows the incumbent losing on every row is
propaganda:

**Ahrefs** — the link index. Nothing free comes close, and for competitive link analysis and
prospecting it is the best tool available. If your work is link-led, buy it.

**Semrush** — breadth and keyword database. Paid search data, PPC intelligence, and
market-level research have no free equivalent.

**Surfer** — a specific, well-tuned content optimisation model refined over years against
outcome data. A local 9B model will not match it on prose scoring.

**Screaming Frog** — a decade of crawler edge cases. JS rendering, log file analysis, and
enormous sites are all handled better than a new crawler will handle them for a while.

**AgencyAnalytics** — dozens of integrations beyond Google. If a client needs Facebook Ads,
LinkedIn, and call tracking in one report, this covers it.

### The honest positioning

> **For agencies with Search Console access to their clients' sites, this replaces 80% of a
> $500/month stack at zero cost, and does two things none of them do: it joins rankings to
> revenue, and it keeps client data on your own machine. It does not replace a link index, and
> it will not out-write a frontier model.**

That sentence is the pitch, and every clause is defensible.

### Why an incumbent won't copy this

Not a moat exactly, but a durable structural asymmetry:

1. **Their business model forbids it.** Ahrefs cannot tell customers "use Search Console
   instead" — it is an argument against their own product.
2. **Local AI doesn't fit SaaS economics.** A GPU per concurrent user is the wrong shape for a
   subscription business.
3. **Agency-shaped workflow needs agency insight.** Diff-first, urgency-sorted, cross-client
   navigation comes from doing the work, not from studying the market.

The asymmetry is real but it is not a defensible business — which is exactly why §51 concludes
the value is in *using* this, not selling it.

---

## §56. Risk Analysis

### Register

| # | Risk | Likelihood | Impact | Score |
|---|---|---|---|---|
| 1 | Google changes/restricts GSC or GA4 APIs | Low | **Critical** | 🔴 |
| 2 | Local model quality insufficient for content | **Medium** | High | 🔴 |
| 3 | Crawler blocked by client WAFs | Medium | Medium | 🟡 |
| 4 | Project stalls before Phase 1 completes | **Medium** | High | 🔴 |
| 5 | SERP scraping stops working entirely | High | Low | 🟡 |
| 6 | Machine failure / theft | Low | High | 🟡 |
| 7 | Maintenance burden exceeds savings | Medium | Medium | 🟡 |
| 8 | Client objects to a non-standard tool | Low | Medium | 🟢 |
| 9 | Data leak between clients | Low | **Critical** | 🔴 |
| 10 | Ollama or Qwen abandoned upstream | Low | Medium | 🟢 |

### The four red risks

**1 — Google API dependency.** The entire data layer rests on APIs Google provides free and
could restrict. Nothing prevents it.

*Mitigation:* the data is **stored locally, permanently**. If GSC's API vanished tomorrow, 16
months of history remain in Postgres and everything except fresh sync keeps working. Also:
Google has strong incentives here — GSC's API existing makes Search Console more valuable, and
withdrawing it would be a significant reversal. **Residual risk accepted.**

**2 — Local model quality.** The highest *likelihood* red. Qwen 3.5 9B may simply not be good
enough for publishable long-form (§5.9).

*Mitigation:* the pipeline design (§17); the honest measurement gate in Sprint 11 (§47); and
the `RemoteProvider` escape hatch. Crucially, **the content module is Phase 4** — if it
disappoints, Phases 1–3 have already delivered the reporting, technical, and research value
that justify the build. The project does not depend on this risk resolving well.

**4 — Project stall.** The most likely way this fails is not technical. Twenty-four weeks of
part-time work while running an agency is a lot, and half-built tools help nobody.

*Mitigation:* phase ordering is explicitly designed so **each phase is independently useful**.
Phase 1 alone (reports) justifies the effort. If work stops at week 12, the agency still has
automated monthly reporting and a technical scanner. This is the single most important risk
mitigation in the entire plan, and it is a sequencing decision, not a technical one.

**9 — Cross-client data leak.** Lowest likelihood, highest consequence — an incident with the
agency's own customers.

*Mitigation:* defence in depth (§28) — application-layer scoping, RLS as an independent
backstop, transaction-scoped session variables, and a dedicated CI job that tests every route
with a mismatched principal (§48). **Accepted as adequately controlled.**

### The amber ones, briefly

**3 — WAF blocking.** Cloudflare and similar may block the crawler. *Mitigation:* identifiable
user agent with a contact URL, polite rates, and the crawl-anomaly detector (§31) which
catches a silent partial crawl. When it happens, ask the client to allowlist — a normal
conversation, since it is their site.

**5 — SERP scraping breaks.** High likelihood, low impact *because the architecture already
assumes it*. GSC is the primary rank source; scraping only serves competitor snapshots.
`ApifyProvider` exists for anyone who needs it to keep working.

**6 — Machine failure.** *Mitigation:* `backup.sh`, and a rehearsed restore (§49). The
restore rehearsal is the mitigation; the script alone is not.

**7 — Maintenance burden.** Real. A tool you maintain is a tool you pay for in time.
*Mitigation:* deliberately boring technology (§37), minimal dependencies, and no distributed
systems. Reassess honestly at six months — if it costs more time than it saves, that is
information, not failure.

### The risk this plan accepts on purpose

**Building software instead of buying it is itself the risk.** Twenty-four weeks of an agency
owner's part-time attention has an opportunity cost that may exceed $12,000 of tool savings.

The counterargument, stated once so it can be judged: the savings recur forever, the capability
is differentiating in pitches, the data joins are genuinely unavailable commercially, and —
being honest about motivation — building it is interesting, which materially raises the odds
it actually gets finished.

---

## §57. Technical Debt Planning

### Debt taken deliberately

| Decision | Debt incurred | When to pay it |
|---|---|---|
| Postgres as queue | Caps at ~10k jobs/day | Only if hosted at scale (§42) |
| pgvector, not Qdrant | Degrades past ~2M vectors | At the §21 triggers |
| No billing | Would need building | Only under Path B (§51) |
| Local-only deploy | No hosted path exists | Only if productised |
| Five fixed roles | Custom roles need a permission matrix | Enterprise request only |
| Gmail SMTP | Won't scale past ~500 emails/day | Multi-tenant only |
| `RemoteProvider` unimplemented | Interface only | When a deliverable genuinely needs it |
| `QdrantStore` unimplemented | Interface only | With the §21 triggers |
| Playwright rendering not default | JS-heavy sites crawl poorly | When a client's site requires it |

**Every one of these is documented as an interface rather than left implicit.** `SerpProvider`,
`LLMProvider`, and `VectorStore` all have a second implementation named and unbuilt. That is
the difference between deferred work and an unpleasant surprise.

### Debt to avoid at all costs

| Anti-pattern | Why it's fatal here |
|---|---|
| Skipping RLS "for now" | Retrofitting means auditing every query ever written |
| Prompts in code, not `prompt_versions` | Loses the ability to trace or compare quality |
| Testing against fixtures, not real client data | Real sites break in ways fixtures never do |
| Weakening the `content_hash` short-circuit | Nightly GPU time balloons; the window stops fitting |
| Letting the model compute numbers | Hallucinated figures in a client report is the worst failure |
| Adding a service to solve a Postgres-shaped problem | Every service added is permanent operational cost |

### The refactor already anticipated

**Crawler rule engine.** Phase 2 will produce ~30 rules as individual functions. By rule 50
this needs a registry with declared severity, dependencies, and per-site enable/disable.

Building the registry up front would be premature; building 50 ad-hoc rules and *then*
refactoring is expensive. **The plan: write rules ad-hoc through Phase 2, refactor to a
registry at the start of Phase 6, before the count passes ~35.** Booked now so it's a scheduled
task rather than a surprise.

### Quarterly debt review

Four questions, honestly answered:

1. Which deferred interface is now actually needed?
2. Which "temporary" workaround has been there over six months?
3. Which dependency is unmaintained or has a better replacement?
4. Which part of this documentation no longer matches the code?

**The fourth is the one that rots fastest.** A spec that has drifted from the implementation is
worse than no spec — it actively misleads. If a phase diverges from this document, update the
document in the same PR (§46, definition of done).

---

[← 12 Roadmap](12-roadmap.md) · [Index](../README.md) · [Next: 14 — Execution →](14-execution.md)
