# AI SEO Operating System

**A complete SEO platform that runs entirely on your own machine. $0/month, unlimited clients.**

Built for Growleads Agency. Replaces Ahrefs, Semrush, Surfer, Screaming Frog, and
AgencyAnalytics with one local dashboard driven by a local AI model.

```
Google Search Console ┐
Google Analytics 4    ├─→  Postgres + pgvector  ─→  Next.js dashboard (localhost:3000)
Google Business       │         ↑                        ↑
Own crawler           ┤    Python worker            AI agents
Lighthouse CLI        ┤    (Postgres queue)         (Ollama + Qwen 3.5 9B)
WordPress REST        ┘
```

**Recurring cost: $0.** No LLM API billing. No data vendor subscriptions. No cloud hosting.
No per-seat SaaS. The AI runs on your Apple M5 GPU; the data comes from Google's own free
APIs and your own crawler.

---

## Read this documentation

```bash
./serve-docs.sh          # → http://localhost:4000
```

Or read the Markdown directly in `docs/`.

---

## The core argument

Google Search Console already gives you — free, unlimited, for every client site you own —
every query the site ranks for, its average position, impressions, clicks, and CTR, by page,
country, device, and date, across 16 months. Plus that site's backlinks.

That is the core of what agencies pay Ahrefs and Semrush $500/month for. And for **your own
clients** it is strictly better data, because Google measures it from its own logs rather
than estimating it from a crawl sample.

This platform is built on that observation. Of the 28 planned modules, **21 work fully at
$0**, 6 are partial, and every gap is specifically *"information about other people's
websites"* — never anything about serving your own clients.

---

## Section index — all 60 sections

| § | Section | File |
|---|---|---|
| 1 | Product Vision | [01-product-vision.md](docs/01-product-vision.md#1-product-vision) |
| 2 | Problems this product solves | [01-product-vision.md](docs/01-product-vision.md#2-problems-this-product-solves) |
| 3 | Target Users | [01-product-vision.md](docs/01-product-vision.md#3-target-users) |
| 4 | User Personas | [01-product-vision.md](docs/01-product-vision.md#4-user-personas) |
| 5 | Complete Feature List | [02-features.md](docs/02-features.md#5-complete-feature-list) |
| 6 | Feature Priority (MVP / Phase 2 / Future) | [02-features.md](docs/02-features.md#6-feature-priority) |
| 7 | Complete User Journey | [03-user-journeys.md](docs/03-user-journeys.md#7-complete-user-journey) |
| 8 | UI Screen List | [04-ui-ux.md](docs/04-ui-ux.md#8-ui-screen-list) |
| 9 | Navigation Structure | [04-ui-ux.md](docs/04-ui-ux.md#9-navigation-structure) |
| 10 | Sidebar Structure | [04-ui-ux.md](docs/04-ui-ux.md#10-sidebar-structure) |
| 11 | Dashboard Layout | [04-ui-ux.md](docs/04-ui-ux.md#11-dashboard-layout) |
| 12 | Every Page Wireframe | [04-ui-ux.md](docs/04-ui-ux.md#12-every-page-wireframe) |
| 13 | Complete Database Schema | [05-database.md](docs/05-database.md#13-complete-database-schema) |
| 14 | ER Diagram | [05-database.md](docs/05-database.md#14-er-diagram) |
| 15 | API Architecture | [06-api-auth.md](docs/06-api-auth.md#15-api-architecture) |
| 16 | Authentication Flow | [06-api-auth.md](docs/06-api-auth.md#16-authentication-flow) |
| 17 | AI Agent Architecture | [07-ai-architecture.md](docs/07-ai-architecture.md#17-ai-agent-architecture) |
| 18 | Prompt Engineering Strategy | [07-ai-architecture.md](docs/07-ai-architecture.md#18-prompt-engineering-strategy) |
| 19 | RAG Architecture | [07-ai-architecture.md](docs/07-ai-architecture.md#19-rag-architecture) |
| 20 | Embedding Strategy | [07-ai-architecture.md](docs/07-ai-architecture.md#20-embedding-strategy) |
| 21 | Vector Database Planning | [07-ai-architecture.md](docs/07-ai-architecture.md#21-vector-database-planning) |
| 22 | AI Memory Strategy | [07-ai-architecture.md](docs/07-ai-architecture.md#22-ai-memory-strategy) |
| 23 | File Storage Strategy | [08-infrastructure.md](docs/08-infrastructure.md#23-file-storage-strategy) |
| 24 | Background Job Architecture | [08-infrastructure.md](docs/08-infrastructure.md#24-background-job-architecture) |
| 25 | Queue System | [08-infrastructure.md](docs/08-infrastructure.md#25-queue-system) |
| 26 | Webhook Architecture | [08-infrastructure.md](docs/08-infrastructure.md#26-webhook-architecture) |
| 27 | Rate Limiting | [08-infrastructure.md](docs/08-infrastructure.md#27-rate-limiting) |
| 28 | Multi Tenant Architecture | [08-infrastructure.md](docs/08-infrastructure.md#28-multi-tenant-architecture) |
| 29 | Security | [09-security-ops.md](docs/09-security-ops.md#29-security) |
| 30 | Logging | [09-security-ops.md](docs/09-security-ops.md#30-logging) |
| 31 | Monitoring | [09-security-ops.md](docs/09-security-ops.md#31-monitoring) |
| 32 | Deployment Architecture | [10-deployment.md](docs/10-deployment.md#32-deployment-architecture) |
| 33 | CI/CD | [10-deployment.md](docs/10-deployment.md#33-cicd) |
| 34 | Docker Architecture | [10-deployment.md](docs/10-deployment.md#34-docker-architecture) |
| 35 | Folder Structure | [10-deployment.md](docs/10-deployment.md#35-folder-structure) |
| 36 | Tech Stack Recommendation | [10-deployment.md](docs/10-deployment.md#36-tech-stack-recommendation) |
| 37 | Why each technology was selected | [10-deployment.md](docs/10-deployment.md#37-why-each-technology-was-selected) |
| 38 | API Cost Breakdown | [11-costs.md](docs/11-costs.md#38-api-cost-breakdown) |
| 39 | AI Cost Breakdown | [11-costs.md](docs/11-costs.md#39-ai-cost-breakdown) |
| 40 | Hosting Cost | [11-costs.md](docs/11-costs.md#40-hosting-cost) |
| 41 | Monthly Cost Estimate | [11-costs.md](docs/11-costs.md#41-monthly-cost-estimate) |
| 42 | Scaling Strategy | [11-costs.md](docs/11-costs.md#42-scaling-strategy) |
| 43 | Performance Optimization | [11-costs.md](docs/11-costs.md#43-performance-optimization) |
| 44 | SEO Strategy for the platform | [11-costs.md](docs/11-costs.md#44-seo-strategy-for-the-platform) |
| 45 | Development Roadmap | [12-roadmap.md](docs/12-roadmap.md#45-development-roadmap) |
| 46 | Sprint Planning | [12-roadmap.md](docs/12-roadmap.md#46-sprint-planning) |
| 47 | GitHub Milestones | [12-roadmap.md](docs/12-roadmap.md#47-github-milestones) |
| 48 | Testing Strategy | [12-roadmap.md](docs/12-roadmap.md#48-testing-strategy) |
| 49 | Production Checklist | [12-roadmap.md](docs/12-roadmap.md#49-production-checklist) |
| 50 | Future AI Features | [13-business.md](docs/13-business.md#50-future-ai-features) |
| 51 | Business Model | [13-business.md](docs/13-business.md#51-business-model) |
| 52 | SaaS Pricing | [13-business.md](docs/13-business.md#52-saas-pricing) |
| 53 | Enterprise Features | [13-business.md](docs/13-business.md#53-enterprise-features) |
| 54 | Agency Features | [13-business.md](docs/13-business.md#54-agency-features) |
| 55 | Competitive Comparison | [13-business.md](docs/13-business.md#55-competitive-comparison) |
| 56 | Risk Analysis | [13-business.md](docs/13-business.md#56-risk-analysis) |
| 57 | Technical Debt Planning | [13-business.md](docs/13-business.md#57-technical-debt-planning) |
| 58 | Complete Development Timeline | [14-execution.md](docs/14-execution.md#58-complete-development-timeline) |
| 59 | Claude Code Implementation Strategy | [14-execution.md](docs/14-execution.md#59-claude-code-implementation-strategy) |
| 60 | Final Development Checklist | [14-execution.md](docs/14-execution.md#60-final-development-checklist) |

---

## Reading paths

**If you're about to start building** → `14-execution.md`, then `12-roadmap.md`, then
`05-database.md`. Those three tell you what to do Monday morning.

**If you want to understand the architecture** → `10-deployment.md` (§36–37) for the stack
and why, then `07-ai-architecture.md` for the AI layer, then `08-infrastructure.md`.

**If you want to check the $0 claim** → `11-costs.md`. Every line item, with the free
alternative named and the three genuine limitations stated plainly.

**If you're deciding whether to build this at all** → `01-product-vision.md` and
`13-business.md` §55 (competitive comparison).

---

## Hardware this is designed for

| | |
|---|---|
| Machine | Apple M5, 16 GB unified memory, 10 cores |
| AI model | Qwen 3.5 9B via Ollama (~5.5 GB resident, Q4) |
| Embeddings | nomic-embed-text (~275 MB) |
| Database | Postgres 16 + pgvector, in Docker |
| Headroom | ~10 GB for Postgres, crawler, and app after the model |

A 14B model fits but starves the crawler and Postgres. 9B is the right size for this box.

---

## Status

Specification complete. No code written yet. See `14-execution.md` §60 for the
pre-development checklist.
