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
 * DESIGN.md layout language: 1200px contained, left-aligned oversized headline
 * at 64px, 96px section gaps, hairline borders instead of shadows, and exactly
 * one acid-lime button on the page.
 */
import Link from "next/link";

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

export function MarketingHome() {
  return (
    <div className="min-h-screen bg-void">
      <PublicHeader />

      <main>
        {/* ── Hero ──────────────────────────────────────────────────
            Left-aligned oversized headline with a link CTA to its right,
            per DESIGN.md's layout section. */}
        <section className="mx-auto max-w-[1200px] px-6 pb-24 pt-24">
          <p className="mono-label uppercase text-fog">
            Search Console + Analytics
          </p>
          <h1 className="mt-6 max-w-3xl text-paper hero max-md:subheading">
            SEO reporting that shows the working.
          </h1>
          <p className="body-base mt-8 max-w-xl text-fog">
            Connect Google Search Console and Google Analytics. Get the
            performance of every client site in one place, refreshed nightly,
            with every figure traceable to the data it came from.
          </p>

          <div className="mt-12 flex flex-wrap items-center gap-4">
            {/* The single acid-lime element on this page. DESIGN.md:
                one primary action per view, never decoration. */}
            <Link
              href="/login"
              className="flex h-10 items-center rounded-md bg-acid-lime px-4 text-void transition-opacity hover:opacity-90"
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
              className="caption flex h-10 items-center rounded-md border border-graphite px-3 text-mist transition-colors hover:border-smoke hover:text-paper"
            >
              How your data is handled →
            </Link>
          </div>
        </section>

        {/* ── How it works ─────────────────────────────────────────── */}
        <section className="border-t border-graphite">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-paper">How it works</h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n} className="card p-6">
                  {/* Step numbers are fog, not lime. DESIGN.md: the accent is
                      "never for decoration" — one action per view owns it. */}
                  <p className="mono-label text-fog">{s.n}</p>
                  <h3 className="body-lg mt-4 text-paper">{s.title}</h3>
                  <p className="body-sm mt-3 text-fog">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Scopes ───────────────────────────────────────────────────
            The section a Google reviewer is looking for: every requested
            permission, named, with the reason, before anyone signs in. */}
        <section className="border-t border-graphite">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-paper">
              What the app asks for, and why
            </h2>
            <p className="body-base mt-4 max-w-xl text-fog">
              Every Google permission is read-only. The app cannot publish,
              change or delete anything in your Search Console or Analytics
              properties.
            </p>

            <div className="mt-12 divide-y divide-graphite border-y border-graphite">
              {SCOPES.map((s) => (
                <div
                  key={s.scope}
                  className="grid gap-3 py-6 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] md:gap-12"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="body-sm text-paper">{s.label}</p>
                      {s.sensitive && (
                        <span className="label rounded-sm bg-white/5 px-1.5 py-0.5 text-fog">
                          sensitive
                        </span>
                      )}
                    </div>
                    <p className="mono-label mt-2 break-words text-ash">
                      {s.scope}
                    </p>
                  </div>
                  <p className="body-sm text-fog">{s.why}</p>
                </div>
              ))}
            </div>

            <p className="body-sm mt-8 max-w-2xl text-ash">
              Sign-in asks only for your name and email. Search Console and
              Analytics access is requested separately, afterwards, on a screen
              that explains each one — so you can see the product before deciding
              to hand it anything.
            </p>
          </div>
        </section>

        {/* ── Data handling ────────────────────────────────────────── */}
        <section className="border-t border-graphite">
          <div className="mx-auto max-w-[1200px] px-6 py-24">
            <h2 className="subheading text-paper">Your data</h2>
            <div className="mt-12 grid gap-8 md:grid-cols-3">
              {PRINCIPLES.map((p) => (
                <div key={p.label}>
                  <p className="mono-label uppercase text-fog">{p.label}</p>
                  <p className="body-sm mt-3 text-mist">{p.body}</p>
                </div>
              ))}
            </div>
            <p className="body-sm mt-12 text-fog">
              Revoke access at any time from your Google account, or ask for
              deletion by email. The full detail is in the{" "}
              <Link
                href="/privacy"
                className="text-mist underline underline-offset-2 hover:text-paper"
              >
                privacy policy
              </Link>
              .
            </p>
          </div>
        </section>
      </main>

      <PublicFooter />
    </div>
  );
}
