import Link from "next/link";
import { redirect } from "next/navigation";

import { systemQuery } from "@/lib/db";
import { describeOAuthError } from "@/lib/oauth-errors";
import { getPrincipal } from "@/lib/session";

import { ConnectForm } from "./connect-form";

export const dynamic = "force-dynamic";

export default async function Connect({
  searchParams,
}: {
  searchParams: Promise<{ partial?: string; oauth_error?: string }>;
}) {
  const principal = await getPrincipal();
  if (!principal) redirect("/login");

  const { partial, oauth_error: oauthError } = await searchParams;
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";

  const [connection] = await systemQuery<{ scopes: string[]; account_email: string }>(
    `SELECT scopes, account_email FROM oauth_connections
     WHERE org_id = $1 AND provider = 'google' AND revoked_at IS NULL
     LIMIT 1`,
    [principal.orgId],
  );

  const scopes = connection?.scopes ?? [];
  const hasGsc = scopes.some((s) => s.includes("webmasters"));
  const hasGa4 = scopes.some((s) => s.includes("analytics"));
  const granted = hasGsc || hasGa4;

  return (
    <div className="min-h-screen">
      <header className="h-16 border-b border-line bg-canvas">
        <div className="mx-auto flex h-full max-w-3xl items-center justify-between px-6">
          <Link href="/" className="body-sm text-title">
            ← Dashboard
          </Link>
          <span className="mono-label text-muted">{principal.orgName}</span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="mono-label mb-3 uppercase text-muted">Connect</p>
        <h1 className="subheading text-title">Add a client site.</h1>
        <p className="body-base mt-3 text-subtle">
          Pull real rankings and traffic from Search Console and Analytics. Your
          Google account must already have access to the properties.
        </p>

        {/* Google refused the data grant and sent the user back. Most often
            they pressed Cancel on the consent screen; this used to land on a
            raw 422 JSON page instead. */}
        {oauthError && (
          <div className="mt-8 rounded-md border border-line bg-fill-subtle px-4 py-3">
            <p className="body-sm text-title">
              Google access wasn&apos;t granted.
            </p>
            <p className="body-sm mt-2 text-subtle">
              {describeOAuthError(oauthError)}
            </p>
          </div>
        )}

        {!granted ? (
          <section className="mt-10 rounded-lg border border-line bg-surface p-6">
            <h2 className="body-emphasis text-title">Grant data access</h2>
            <p className="body-sm mt-2 text-subtle">
              Signing in only gave us your email. Reading a client&apos;s data
              needs two more scopes, requested separately so you can see exactly
              what they are.
            </p>

            <ul className="mt-5 space-y-3">
              <li className="flex gap-3">
                <span className="mono-label mt-0.5 text-muted">01</span>
                <div>
                  <p className="body-sm text-title">
                    Search Console — read only
                  </p>
                  <p className="body-sm text-subtle">
                    Queries, positions, clicks, impressions. 16 months of history.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="mono-label mt-0.5 text-muted">02</span>
                <div>
                  <p className="body-sm text-title">Analytics — read only</p>
                  <p className="body-sm text-subtle">
                    Sessions, conversions and revenue, joined to rankings by
                    landing page.
                  </p>
                </div>
              </li>
            </ul>

            <a
              href={`${apiUrl}/v1/google/grant`}
              className="mt-6 inline-flex h-10 items-center rounded-md bg-accent px-4 text-on-accent transition-opacity hover:opacity-90"
              style={{ fontSize: 14, fontWeight: 510, letterSpacing: "-0.011em" }}
            >
              Grant access
            </a>

            {/* Was "no data leaves this machine" — true of a laptop install,
                false once this is hosted for other people. */}
            <p className="caption mt-4 text-muted">
              Read-only. Nothing is written to your Google account, and your
              data is never sold or shared.
            </p>
          </section>
        ) : (
          <>
            {/* These two carried Vercel-era warning tokens that no longer
                exist, so the panel rendered unstyled after the design change.
                Neutral chrome is right here anyway: a partial grant is a
                state to resolve, not an error. */}
            {partial && (
              <div className="mt-8 rounded-md border border-line bg-fill-subtle px-4 py-3">
                <p className="body-sm text-title">
                  Only some permissions were granted
                  {!hasGsc && " — Search Console is missing"}
                  {!hasGa4 && " — Analytics is missing"}.
                </p>
                <p className="body-sm mt-2 text-subtle">
                  You can still continue with what was granted, or{" "}
                  <a
                    href={`${apiUrl}/v1/google/grant`}
                    className="text-body underline underline-offset-2 hover:text-title"
                  >
                    grant the rest
                  </a>
                  .
                </p>
              </div>
            )}

            <div className="mt-8 flex items-center gap-2">
              <span className="mono-label rounded-full bg-surface-3 px-2 py-1 text-subtle">
                {connection.account_email}
              </span>
              <span className="mono-label text-muted">
                {hasGsc ? "Search Console ✓" : "Search Console ✗"} ·{" "}
                {hasGa4 ? "Analytics ✓" : "Analytics ✗"}
              </span>
            </div>

            <ConnectForm apiUrl={apiUrl} />
          </>
        )}
      </main>
    </div>
  );
}
