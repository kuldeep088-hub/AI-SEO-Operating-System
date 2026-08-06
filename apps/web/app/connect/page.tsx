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
      <header className="h-16 border-b border-hairline bg-canvas">
        <div className="mx-auto flex h-full max-w-3xl items-center justify-between px-6">
          <Link href="/" className="body-sm-strong text-ink">
            ← Dashboard
          </Link>
          <span className="caption-mono text-mute">{principal.orgName}</span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="caption-mono mb-3 uppercase text-mute">Connect</p>
        <h1 className="display-lg text-ink">Add a client site.</h1>
        <p className="body-md mt-3 text-body">
          Pull real rankings and traffic from Search Console and Analytics. Your
          Google account must already have access to the properties.
        </p>

        {!granted ? (
          <section className="mt-10 rounded-md border border-hairline bg-canvas p-6">
            <h2 className="display-sm text-ink">Grant data access</h2>
            <p className="body-sm mt-2 text-body">
              Signing in only gave us your email. Reading a client&apos;s data
              needs two more scopes, requested separately so you can see exactly
              what they are.
            </p>

            <ul className="mt-5 space-y-3">
              <li className="flex gap-3">
                <span className="caption-mono mt-0.5 text-mute">01</span>
                <div>
                  <p className="body-sm-strong text-ink">
                    Search Console — read only
                  </p>
                  <p className="body-sm text-body">
                    Queries, positions, clicks, impressions. 16 months of history.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="caption-mono mt-0.5 text-mute">02</span>
                <div>
                  <p className="body-sm-strong text-ink">Analytics — read only</p>
                  <p className="body-sm text-body">
                    Sessions, conversions and revenue, joined to rankings by
                    landing page.
                  </p>
                </div>
              </li>
            </ul>

            <a
              href={`${apiUrl}/v1/google/grant`}
              className="elevate-1 mt-6 inline-flex h-10 items-center rounded-sm bg-primary px-4 text-on-primary transition-opacity hover:opacity-90"
            >
              <span className="body-sm-strong">Grant access</span>
            </a>

            <p className="caption mt-4 text-mute">
              Read-only. Nothing is written to your Google account, and no data
              leaves this machine.
            </p>
          </section>
        ) : (
          <>
            {partial && (
              <div className="mt-8 rounded-sm border border-warning-soft bg-warning-soft/40 px-4 py-3">
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
              <span className="caption-mono rounded-full bg-canvas-soft-2 px-2 py-1 text-body">
                {connection.account_email}
              </span>
              <span className="caption-mono text-mute">
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
