/**
 * The public homepage — what a logged-out visitor sees at "/".
 *
 * Google's OAuth verification requires a homepage that is publicly reachable
 * (no sign-in wall), hosted on the verified domain, that explains what the app
 * does and links to the privacy policy. It also requires that the use of each
 * sensitive scope be evident to a reviewer who has never used the product,
 * which is why the scopes are named on the page rather than buried in the
 * consent screen.
 *
 * On claims: only Phase 0 and the Phase 1 data pipeline exist today — there is
 * no crawler, no AI layer and no report generator yet (docs/12-roadmap.md).
 * The page therefore separates what works now from what is planned, rather
 * than describing the finished vision in the present tense. A reviewer opens
 * the app and compares it against this page, and so does a customer.
 *
 * DESIGN.md layout language: 1200px contained, left-aligned oversized headline,
 * 96px section gaps, hairline borders instead of shadows, and exactly one
 * acid-lime button on the page.
 */
import Link from "next/link";

import { ProductPreview } from "@/components/product-preview";
import { PublicFooter, PublicHeader } from "@/components/public-chrome";
import { SCOPES } from "@/lib/company";

const STEPS = [
  {
    n: "01",
    title: "Connect Google",
    body: "Sign in, then grant read-only access to the Search Console and Analytics properties you choose. Each permission is explained before it is requested.",
  },
  {
    n: "02",
    title: "It backfills, then keeps up",
    body: "Sixteen months of history is pulled once, then a scheduled sync runs every night so the numbers are current before anyone opens a dashboard.",
  },
  {
    n: "03",
    title: "Read what changed",
    body: "Clicks, impressions, average position and conversions per page and per query — with the previous period alongside, so a number never appears without its context.",
  },
];

const CAPABILITIES = [
  {
    title: "Every client in one view",
    body: "One dashboard across all connected sites, ordered so the ones needing attention sit at the top. No switching accounts, no per-client logins.",
  },
  {
    title: "Nightly sync, unattended",
    body: "A scheduler fires per site at 02:00 local time, staggered by a deterministic per-site offset so fifteen properties do not hit Google's API in the same minute.",
  },
  {
    title: "Period-over-period by default",
    body: "Every figure ships with the previous 28 days beside it. A number without a comparison is not information, so the UI does not offer one.",
  },
  {
    title: "Sixteen months of history",
    body: "The initial backfill pulls Search Console's full retention window, so trends are visible on day one rather than after a quarter of waiting.",
  },
  {
    title: "Correlation, never causation",
    body: "Where two things happened on the same date, the app says so. It does not tell you one caused the other, because the data cannot support that claim.",
  },
  {
    title: "Tenants stay separated",
    body: "Isolation between organisations is enforced by PostgreSQL row-level security in the database itself, not by application code that could forget a filter.",
  },
];

const ROADMAP = [
  {
    phase: "Available now",
    items:
      "Search Console and Analytics sync, 16-month backfill, nightly scheduling, multi-client dashboard",
    live: true,
  },
  {
    phase: "Next",
    items: "Technical crawler, Lighthouse audits, issue tracking",
    live: false,
  },
  {
    phase: "Planned",
    items: "Written monthly reports, keyword research, content briefs",
    live: false,
  },
];

const PRINCIPLES = [
  {
    label: "Not sold",
    body: "No advertising networks, no trackers on this app, no data brokers. The only outbound calls carrying your data go back to Google's own APIs.",
  },
  {
    label: "Encrypted",
    body: "Google tokens are encrypted at rest with a key held outside the database, so a copy of the database alone grants nobody access to your Google account.",
  },
  {
    label: "Separated",
    body: "Each organisation's rows are isolated by PostgreSQL row-level security — enforced by the database, not by application code that could forget.",
  },
];

const FAQ = [
  {
    q: "Can the app change anything in my Search Console or Analytics?",
    a: "No. Both scopes are read-only — webmasters.readonly and analytics.readonly. There is no write permission to grant, so there is nothing to misuse: it cannot submit sitemaps, request indexing, alter property settings or delete data.",
  },
  {
    q: "What happens if I revoke access?",
    a: "Syncing stops immediately. You can revoke from your Google account permissions page or disconnect inside the app; either way the stored tokens become useless and are deleted on the next sync attempt. Nothing further is fetched.",
  },
  {
    q: "Do you train AI models on my data?",
    a: "No, and the privacy policy says so without qualification. The reporting layer is designed to run a local model against your own data rather than send it to a third-party API.",
  },
  {
    q: "Can I connect a client property I don't own?",
    a: "Only if they have granted your Google account access to it in Search Console. The app inherits exactly the properties your account can already see — it cannot obtain access you do not have.",
  },
  {
    q: "How do I delete everything?",
    a: "Email the contact address on the privacy policy from your sign-up address. Deletion is permanent, covers the cached Search Console and Analytics data, and completes within 30 days. Encrypted backups rotate on a 14-day cycle, so a copy may persist for that long.",
  },
];

export function MarketingHome() {
  return (
    <div className="min-h-screen bg-canvas">
      <PublicHeader />

      <main>
        {/* ── Hero ────────────────────────────────────────────────── */}
        <section className="mx-auto max-w-[1200px] px-6 pb-16 pt-24">
          <p className="mono-label uppercase text-subtle">
            Search Console + Analytics
          </p>
          <h1 className="mt-6 max-w-3xl text-title hero max-md:subheading">
            SEO reporting that shows the working.
          </h1>
          <p className="body-base mt-8 max-w-xl text-subtle">
            Connect Google Search Console and Google Analytics. Get the
            performance of every client site in one place, refreshed nightly,
            with every figure traceable to the data it came from.
          </p>

          <div className="mt-12 flex flex-wrap items-center gap-4">
            {/* The single acid-lime element on this page. DESIGN.md:
                one primary action per view, never decoration. */}
            <Link
              href="/login"
              className="flex h-10 items-center rounded-md bg-accent px-4 text-on-accent transition-opacity hover:opacity-90"
              style={{
                fontSize: 14,
                fontWeight: 510,
                letterSpacing: "-0.011em",
                boxShadow: "var(--shadow-cta)",
              }}
            >
              Continue with Google
            </Link>
            <Link
              href="/privacy"
              className="caption flex h-10 items-center rounded-md border border-line px-3 text-body transition-colors hover:border-line-strong hover:text-title"
            >
              How your data is handled →
            </Link>
          </div>

          <div className="mt-20">
            <ProductPreview />
          </div>
        </section>

        {/* ── How it works ─────────────────────────────────────────── */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">How it works</h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n} className="card p-6">
                  {/* Step numbers are subtle, not lime. DESIGN.md: the accent
                      is "never for decoration" — one action per view owns it. */}
                  <p className="mono-label text-subtle">{s.n}</p>
                  <h3 className="body-lg mt-4 text-title">{s.title}</h3>
                  <p className="body-sm mt-3 text-subtle">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Capabilities ─────────────────────────────────────────── */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">What you get</h2>
            <p className="body-base mt-4 max-w-xl text-subtle">
              Built for people who run SEO for other people, and have to explain
              the numbers afterwards.
            </p>
            <div className="mt-12 grid gap-x-12 gap-y-10 md:grid-cols-2 lg:grid-cols-3">
              {CAPABILITIES.map((c) => (
                <div key={c.title}>
                  <h3 className="body-lg text-title">{c.title}</h3>
                  <p className="body-sm mt-2 text-subtle">{c.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Honest status ────────────────────────────────────────────
            Stating plainly what is not built yet. Overstating it to a Google
            reviewer — who opens the app and compares — is a bad trade for a
            line of copy, and it is a bad trade for a customer too. */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">Where the product is</h2>
            <p className="body-base mt-4 max-w-xl text-subtle">
              It is being built in the open. This is what exists today and what
              is coming, so you can judge whether it is useful to you yet.
            </p>
            <div className="mt-12 divide-y divide-line border-y border-line">
              {ROADMAP.map((r) => (
                <div
                  key={r.phase}
                  className="grid gap-3 py-6 md:grid-cols-[minmax(0,1fr)_minmax(0,3fr)] md:gap-12"
                >
                  <div className="flex items-start gap-2">
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        r.live ? "bg-positive" : "bg-muted"
                      }`}
                    />
                    <p className="body-sm text-title">{r.phase}</p>
                  </div>
                  <p className="body-sm text-subtle">{r.items}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Scopes ───────────────────────────────────────────────────
            The section a Google reviewer is looking for: every requested
            permission, named, with the reason, before anyone signs in. */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">
              What the app asks for, and why
            </h2>
            <p className="body-base mt-4 max-w-xl text-subtle">
              Every Google permission is read-only. The app cannot publish,
              change or delete anything in your Search Console or Analytics
              properties.
            </p>

            <div className="mt-12 divide-y divide-line border-y border-line">
              {SCOPES.map((s) => (
                <div
                  key={s.scope}
                  className="grid gap-3 py-6 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] md:gap-12"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="body-sm text-title">{s.label}</p>
                      {s.sensitive && (
                        <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
                          sensitive
                        </span>
                      )}
                    </div>
                    <p className="mono-label mt-2 break-words text-muted">
                      {s.scope}
                    </p>
                  </div>
                  <p className="body-sm text-subtle">{s.why}</p>
                </div>
              ))}
            </div>

            <p className="body-sm mt-8 max-w-2xl text-muted">
              Sign-in asks only for your name and email. Search Console and
              Analytics access is requested separately, afterwards, on a screen
              that explains each one — so you can see the product before deciding
              to hand it anything.
            </p>
          </div>
        </section>

        {/* ── Data handling ────────────────────────────────────────── */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">Your data</h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {PRINCIPLES.map((p) => (
                <div key={p.label}>
                  <p className="mono-label uppercase text-subtle">{p.label}</p>
                  <p className="body-sm mt-3 text-body">{p.body}</p>
                </div>
              ))}
            </div>
            <p className="body-sm mt-12 text-subtle">
              Revoke access at any time from your Google account, or ask for
              deletion by email. The full detail is in the{" "}
              <Link
                href="/privacy"
                className="text-body underline underline-offset-2 hover:text-title"
              >
                privacy policy
              </Link>
              .
            </p>
          </div>
        </section>

        {/* ── FAQ ──────────────────────────────────────────────────────
            <details> rather than JS accordion state: it works before
            hydration, it is keyboard accessible for free, and the answers
            stay in the DOM for anyone searching the page with ⌘F. */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-title">Questions</h2>
            <div className="mt-12 max-w-3xl divide-y divide-line border-y border-line">
              {FAQ.map((f) => (
                <details key={f.q} className="group py-5">
                  <summary className="flex cursor-pointer list-none items-start justify-between gap-6 text-title">
                    <span className="body-sm">{f.q}</span>
                    <span
                      aria-hidden="true"
                      className="mt-0.5 shrink-0 text-subtle transition-transform group-open:rotate-45"
                    >
                      +
                    </span>
                  </summary>
                  <p className="body-sm mt-3 max-w-2xl text-subtle">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* ── Closing CTA ──────────────────────────────────────────────
            Neutral inverse pill, not a second acid-lime button — the hero
            already spent the page's one primary action. */}
        <section className="border-t border-line">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading max-w-2xl text-title">
              Connect a property and see the last sixteen months tonight.
            </h2>
            <p className="body-base mt-4 max-w-xl text-subtle">
              Read-only access, revocable at any time, and nothing to install.
            </p>
            <Link
              href="/login"
              className="mt-10 inline-flex h-10 items-center rounded-full bg-inverse px-5 text-on-inverse transition-opacity hover:opacity-90"
              style={{ fontSize: 13, fontWeight: 510, letterSpacing: "-0.011em" }}
            >
              Continue with Google
            </Link>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
