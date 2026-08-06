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
 * DESIGN.md §"Vercel is a developer-platform brand": marketing CTAs take the
 * 100px pill; the 6px nav square is for in-app chrome. Both appear on this
 * page only in their correct roles.
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

export function MarketingHome() {
  return (
    <div className="min-h-screen bg-canvas-soft">
      <PublicHeader />

      <main>
        {/* ── Hero ────────────────────────────────────────────────── */}
        <section className="mx-auto max-w-5xl px-6 py-24">
          <p className="caption-mono uppercase text-mute">
            Search Console + Analytics, in one place
          </p>
          <h1 className="display-xl mt-4 max-w-2xl text-ink">
            SEO reporting that shows the working.
          </h1>
          <p className="body-md mt-6 max-w-xl text-body">
            Connect Google Search Console and Google Analytics. Get the
            performance of every client site in one dashboard, refreshed nightly,
            with every figure traceable to the data it came from.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <Link
              href="/login"
              className="elevate-1 flex h-12 items-center rounded-full bg-primary px-7 text-on-primary transition-opacity hover:opacity-90"
            >
              <span className="body-sm-strong">Continue with Google</span>
            </Link>
            <Link
              href="/privacy"
              className="flex h-12 items-center rounded-full border border-hairline-strong bg-canvas px-7 text-ink transition-colors hover:bg-canvas-soft-2"
            >
              <span className="body-sm-strong">How your data is handled</span>
            </Link>
          </div>
        </section>

        {/* ── How it works ────────────────────────────────────────── */}
        <section className="border-t border-hairline bg-canvas">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="display-md text-ink">How it works</h2>
            <div className="mt-10 grid gap-8 sm:grid-cols-3">
              {STEPS.map((s) => (
                <div key={s.n}>
                  <p className="caption-mono text-mute">{s.n}</p>
                  <h3 className="body-sm-strong mt-3 text-ink">{s.title}</h3>
                  <p className="body-sm mt-2 text-body">{s.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Scopes ──────────────────────────────────────────────────
            The section a Google reviewer is looking for: every requested
            permission, named, with the reason, before anyone signs in. */}
        <section className="border-t border-hairline">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="display-md text-ink">
              What the app asks for, and why
            </h2>
            <p className="body-md mt-3 max-w-xl text-body">
              Every Google permission is read-only. The app cannot publish,
              change or delete anything in your Search Console or Analytics
              properties.
            </p>

            <div className="mt-10 divide-y divide-hairline border-y border-hairline">
              {SCOPES.map((s) => (
                <div
                  key={s.scope}
                  className="grid gap-2 py-6 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] sm:gap-8"
                >
                  <div>
                    <p className="body-sm-strong text-ink">{s.label}</p>
                    <p className="caption-mono mt-1 break-words text-mute">
                      {s.scope}
                    </p>
                  </div>
                  <p className="body-sm text-body">{s.why}</p>
                </div>
              ))}
            </div>

            <p className="body-sm mt-6 text-mute">
              Sign-in asks only for your name and email. Search Console and
              Analytics access is requested separately, afterwards, on a screen
              that explains each one — so you can see the product before deciding
              to hand it anything.
            </p>
          </div>
        </section>

        {/* ── Data handling ───────────────────────────────────────── */}
        <section className="border-t border-hairline bg-canvas">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <h2 className="display-md text-ink">Your data</h2>
            <div className="mt-8 grid gap-8 sm:grid-cols-3">
              <div>
                <p className="caption-mono uppercase text-mute">Not sold</p>
                <p className="body-sm mt-2 text-body">
                  No advertising networks, no trackers on this app, no data
                  brokers. The only outbound calls carrying your data go back to
                  Google&rsquo;s own APIs.
                </p>
              </div>
              <div>
                <p className="caption-mono uppercase text-mute">Encrypted</p>
                <p className="body-sm mt-2 text-body">
                  Google tokens are encrypted at rest with a key held outside the
                  database, so a copy of the database alone grants nobody access
                  to your Google account.
                </p>
              </div>
              <div>
                <p className="caption-mono uppercase text-mute">Separated</p>
                <p className="body-sm mt-2 text-body">
                  Each organisation&rsquo;s rows are isolated by PostgreSQL
                  row-level security — enforced by the database, not by
                  application code that could forget.
                </p>
              </div>
            </div>
            <p className="body-sm mt-8 text-body">
              Revoke access at any time from your Google account, or ask for
              deletion by email. The full detail is in the{" "}
              <Link href="/privacy" className="text-link underline">
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
