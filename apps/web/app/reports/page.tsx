import Link from "next/link";
import { redirect } from "next/navigation";

import { Empty, Panel } from "@/components/analytics-parts";
import { ThemeToggle } from "@/components/theme-toggle";
import { tenantQuery } from "@/lib/db";
import { getPrincipal } from "@/lib/session";

export const dynamic = "force-dynamic";

type ReportRow = {
  id: string;
  domain: string;
  client_name: string;
  period_start: string;
  period_end: string;
  state: string;
  created_at: string;
  clicks: number | string | null;
};

function fmtPeriod(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  return `${s.toLocaleDateString(undefined, opts)} – ${e.toLocaleDateString(undefined, { ...opts, year: "numeric" })}`;
}

export default async function Reports() {
  const principal = await getPrincipal();
  if (!principal) redirect("/login");

  const reports = await tenantQuery<ReportRow>(
    principal.orgId,
    principal.role,
    `SELECT r.id, s.domain, c.name AS client_name,
            r.period_start::text, r.period_end::text, r.state,
            r.created_at::text,
            -- Read out of the stored payload rather than recomputed: the
            -- report is a snapshot, and later syncs must not change what a
            -- sent report said.
            r.data #>> '{totals,clicks}' AS clicks
     FROM   reports r
     JOIN   sites s   ON s.id = r.site_id
     JOIN   clients c ON c.id = s.client_id
     WHERE  r.kind = 'monthly'
     ORDER  BY r.period_start DESC, r.created_at DESC`,
  );

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 h-16 border-b border-line bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href="/" className="caption text-body hover:text-title">
              ← Dashboard
            </Link>
            <span className="body-sm text-title">Reports</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-10">
        <p className="mono-label uppercase text-muted">Monthly</p>
        <h1 className="subheading mt-2 text-title">Client reports</h1>
        <p className="body-sm mt-3 max-w-xl text-subtle">
          Generated from Search Console and Analytics, with the narrative written
          by the local model against figures calculated in SQL.
        </p>

        <div className="mt-10">
          <Panel title="All reports" hint={`${reports.length} total`}>
            {reports.length === 0 ? (
              <Empty>
                No reports yet. They are generated on the 3rd of each month for
                the previous month, or on demand from a site&rsquo;s page.
              </Empty>
            ) : (
              <div className="divide-y divide-line">
                {reports.map((r) => (
                  <Link
                    key={r.id}
                    href={`/reports/${r.id}`}
                    className="flex flex-wrap items-baseline justify-between gap-3 py-4 hover:bg-fill-subtle"
                  >
                    <div className="min-w-0">
                      <p className="body-sm text-title">{r.client_name}</p>
                      <p className="mono-label mt-1 text-muted">{r.domain}</p>
                    </div>
                    <div className="flex items-baseline gap-6">
                      <span className="caption text-subtle">
                        {fmtPeriod(r.period_start, r.period_end)}
                      </span>
                      <span className="caption tnum text-title">
                        {Number(r.clicks ?? 0).toLocaleString()} clicks
                      </span>
                      <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
                        {r.state}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </main>
    </div>
  );
}
