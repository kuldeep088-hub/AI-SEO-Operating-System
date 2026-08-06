import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { PrintButton } from "@/components/print-button";
import { ThemeToggle } from "@/components/theme-toggle";
import { tenantQuery } from "@/lib/db";
import { getPrincipal } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * A single monthly report — the Phase 1 deliverable.
 *
 * Everything shown comes out of `reports.data` and `reports.narrative`, which
 * are a snapshot taken when the report was generated. Nothing is recomputed
 * from `gsc_daily` on render: a report that silently changes its numbers after
 * it has been sent to a client is worse than no report.
 *
 * PDF is the browser's own print-to-PDF rather than a headless Chrome
 * pipeline. `@media print` in globals.css drops the chrome, and it keeps the
 * `$0/month` constraint intact with no runtime binary to install.
 */

type Narrative = {
  summary: string;
  sections: { heading: string; body: string }[];
  confidence: string;
  data_caveat?: string;
  _meta?: { model?: string; prompt_version?: number; causal_violations?: string[] };
};

type Totals = {
  clicks: number;
  prev_clicks: number;
  clicks_change_pct: number | null;
  impressions: number;
  prev_impressions: number;
  impressions_change_pct: number | null;
  ctr_pct: number | null;
  avg_position: number | null;
  position_change: number | null;
};

type ReportData = {
  site: { domain: string; client_name: string };
  period_start: string;
  period_end: string;
  days_with_data: number;
  totals: Totals;
  top_queries: { query: string; clicks: number; impressions: number; position: string }[];
  top_pages: { page: string; clicks: number; impressions: number }[];
  analytics: Record<string, number | null> | null;
};

function Figure({
  label,
  value,
  change,
  lowerIsBetter,
}: {
  label: string;
  value: string;
  change?: number | null;
  lowerIsBetter?: boolean;
}) {
  const good = change === null || change === undefined
    ? null
    : lowerIsBetter
      ? change <= 0
      : change >= 0;
  return (
    <div className="bg-surface px-5 py-4">
      <p className="mono-label uppercase text-muted">{label}</p>
      <p
        className="tnum mt-2 text-title"
        style={{ fontSize: 24, fontWeight: 510, letterSpacing: "-0.012em" }}
      >
        {value}
      </p>
      {change !== null && change !== undefined && (
        <p
          className={`label tnum mt-1 ${good ? "text-positive" : "text-negative"}`}
        >
          {/* Arrow as well as colour, so direction survives without hue. */}
          {good ? "↑" : "↓"} {Math.abs(change).toFixed(1)}
          {lowerIsBetter ? "" : "%"}
        </p>
      )}
    </div>
  );
}

export default async function Report({
  params,
}: {
  params: Promise<{ reportId: string }>;
}) {
  const principal = await getPrincipal();
  if (!principal) redirect("/login");

  const { reportId } = await params;
  const [row] = await tenantQuery<{
    id: string;
    data: ReportData;
    narrative: Narrative;
    state: string;
    created_at: string;
  }>(
    principal.orgId,
    principal.role,
    `SELECT id, data, narrative, state, created_at::text
     FROM reports WHERE id = $1 AND kind = 'monthly'`,
    [reportId],
  );

  if (!row) notFound();

  // pg returns jsonb already parsed; guard for the string case anyway.
  const data: ReportData =
    typeof row.data === "string" ? JSON.parse(row.data) : row.data;
  const narrative: Narrative =
    typeof row.narrative === "string" ? JSON.parse(row.narrative) : row.narrative;
  const t = data.totals;

  const period = `${new Date(data.period_start).toLocaleDateString(undefined, { day: "numeric", month: "long" })} – ${new Date(data.period_end).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}`;

  return (
    <div className="min-h-screen">
      <header className="no-print sticky top-0 z-10 h-16 border-b border-line bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[900px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Link href="/reports" className="caption text-body hover:text-title">
              ← Reports
            </Link>
            <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
              {row.state}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <PrintButton />
          </div>
        </div>
      </header>

      <main className="report-sheet mx-auto max-w-[900px] px-6 py-12">
        <p className="mono-label uppercase text-muted">Monthly report</p>
        <h1 className="subheading mt-2 text-title">{data.site.client_name}</h1>
        <p className="body-sm mt-1 text-subtle">
          {data.site.domain} · {period}
        </p>

        <section className="mt-10 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-4">
          <Figure
            label="Clicks"
            value={t.clicks.toLocaleString()}
            change={t.clicks_change_pct}
          />
          <Figure
            label="Impressions"
            value={t.impressions.toLocaleString()}
            change={t.impressions_change_pct}
          />
          <Figure
            label="CTR"
            value={t.ctr_pct === null ? "—" : `${t.ctr_pct.toFixed(2)}%`}
          />
          <Figure
            label="Avg position"
            value={t.avg_position === null ? "—" : t.avg_position.toFixed(1)}
            change={t.position_change}
            lowerIsBetter
          />
        </section>

        <section className="mt-12">
          <h2 className="body-lg text-title">Summary</h2>
          <p className="body-base mt-3 text-body">{narrative.summary}</p>
        </section>

        {narrative.sections.map((s) => (
          <section key={s.heading} className="mt-10">
            <h2 className="body-lg text-title">{s.heading}</h2>
            <p className="body-base mt-3 text-body">{s.body}</p>
          </section>
        ))}

        {data.top_queries.length > 0 && (
          <section className="mt-12">
            <h2 className="body-lg text-title">Top queries</h2>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[420px]">
                <thead>
                  <tr className="border-b border-line">
                    {["Query", "Clicks", "Impressions", "Position"].map((h, i) => (
                      <th
                        key={h}
                        className={`mono-label px-2 pb-2 uppercase text-muted ${i ? "text-right" : "text-left"}`}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.top_queries.slice(0, 10).map((q, i) => (
                    <tr key={q.query} className={i ? "border-t border-line" : ""}>
                      <td className="caption max-w-[240px] truncate px-2 py-2.5 text-title">
                        {q.query}
                      </td>
                      <td className="caption tnum px-2 py-2.5 text-right">
                        {Number(q.clicks).toLocaleString()}
                      </td>
                      <td className="caption tnum px-2 py-2.5 text-right">
                        {Number(q.impressions).toLocaleString()}
                      </td>
                      <td className="caption tnum px-2 py-2.5 text-right">
                        {Number(q.position).toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        <footer className="mt-14 border-t border-line pt-6">
          {narrative.data_caveat && (
            <p className="body-sm text-subtle">{narrative.data_caveat}</p>
          )}
          {/* CLAUDE.md rule 7, stated to the reader rather than only enforced
              in code. A client should know what kind of claim this is. */}
          <p className="body-sm mt-3 text-muted">
            Figures come from Google Search Console and Google Analytics for the
            period shown, and cover {data.days_with_data} days with data. Where
            two things changed in the same period this report says so; it does
            not claim that one caused the other.
          </p>
          <p className="caption mt-3 text-muted">
            Narrative written by {narrative._meta?.model ?? "a local model"} from
            figures calculated in the database
            {narrative._meta?.prompt_version
              ? ` · prompt v${narrative._meta.prompt_version}`
              : ""}
            .
          </p>
        </footer>
      </main>
    </div>
  );
}

