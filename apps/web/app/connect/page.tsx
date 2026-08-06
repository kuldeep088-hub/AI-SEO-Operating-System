import Link from "next/link";
import { redirect } from "next/navigation";

import { systemQuery } from "@/lib/db";
import { getPrincipal } from "@/lib/session";

import { ConnectForm } from "./connect-form";

export const dynamic = "force-dynamic";

export default async function Connect({
  searchParams,
}: {
  searchParams: Promise<{ partial?: string }>;
}) {
  const principal = await getPrincipal();
  if (!principal) redirect("/login");

  const { partial } = await searchParams;
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
      <header className="h-16 border-b border-graphite bg-void">
        <div className="mx-auto flex h-full max-w-3xl items-center justify-between px-6">
          <Link href="/" className="body-sm text-paper">
            ← Dashboard
          </Link>
          <span className="mono-label text-ash">{principal.orgName}</span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="mono-label mb-3 uppercase text-ash">Connect</p>
        <h1 className="subheading text-paper">Add a client site.</h1>
        <p className="body-base mt-3 text-fog">
          Pull real rankings and traffic from Search Console and Analytics. Your
          Google account must already have access to the properties.
        </p>

        {!granted ? (
          <section className="mt-10 rounded-lg border border-graphite bg-carbon p-6">
            <h2 className="body-emphasis text-paper">Grant data access</h2>
            <p className="body-sm mt-2 text-fog">
              Signing in only gave us your email. Reading a client&apos;s data
              needs two more scopes, requested separately so you can see exactly
              what they are.
            </p>

            <ul className="mt-5 space-y-3">
              <li className="flex gap-3">
                <span className="mono-label mt-0.5 text-ash">01</span>
                <div>
                  <p className="body-sm text-paper">
                    Search Console — read only
                  </p>
                  <p className="body-sm text-fog">
                    Queries, positions, clicks, impressions. 16 months of history.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="mono-label mt-0.5 text-ash">02</span>
                <div>
                  <p className="body-sm text-paper">Analytics — read only</p>
                  <p className="body-sm text-fog">
                    Sessions, conversions and revenue, joined to rankings by
                    landing page.
                  </p>
                </div>
              </li>
            </ul>

            <a
              href={`${apiUrl}/v1/google/grant`}
              className="card mt-6 inline-flex h-10 items-center rounded-md bg-acid-lime px-4 text-void transition-opacity hover:opacity-90"
            >
              <span className="body-sm">Grant access</span>
            </a>

            <p className="caption mt-4 text-ash">
              Read-only. Nothing is written to your Google account, and no data
              leaves this machine.
            </p>
          </section>
        ) : (
          <>
            {partial && (
              <div className="mt-8 rounded-md border border-warning-soft bg-warning-soft/40 px-4 py-3">
                <p className="body-sm text-warning-deep">
                  Only some scopes were granted
                  {!hasGsc && " — Search Console is missing"}
                  {!hasGa4 && " — Analytics is missing"}.{" "}
                  <a href={`${apiUrl}/v1/google/grant`} className="underline">
                    Grant the rest
                  </a>
                  .
                </p>
              </div>
            )}

            <div className="mt-8 flex items-center gap-2">
              <span className="mono-label rounded-full bg-slate px-2 py-1 text-fog">
                {connection.account_email}
              </span>
              <span className="mono-label text-ash">
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
