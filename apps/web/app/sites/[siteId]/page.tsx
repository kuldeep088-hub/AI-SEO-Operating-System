import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import {
  BarRow,
  DataTable,
  Delta,
  Empty,
  Panel,
  PositionDelta,
  Stat,
} from "@/components/analytics-parts";
import { ThemeToggle } from "@/components/theme-toggle";
import { TrendChart, type TrendPoint } from "@/components/trend-chart";
import { tenantQuery } from "@/lib/db";
import { getPrincipal } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * Per-site Search Console + Analytics screen — docs/12-roadmap.md Phase 1
 * week 6 ("Search Console analytics screen, query/page explorer, opportunity
 * scoring").
 *
 * Every figure is aggregated in SQL, not in JavaScript. That is not only about
 * speed: gsc_daily is partitioned and holds a row per (date, query, page,
 * country, device), so a month for a mid-sized site is far more rows than
 * belong in a server component's memory. The database also has the indexes.
 *
 * Every query goes through tenantQuery. oauth_connections taught this lesson
 * the expensive way — a tenant table read without an org context returns zero
 * rows and looks exactly like "no data yet".
 */

const WINDOW = 28;
const TREND_DAYS = 90;

type Row = Record<string, string | number | null>;

const n = (v: unknown) => Number(v ?? 0);

function pctChange(now: number, prev: number): number | null {
  if (!prev) return null;
  return ((now - prev) / prev) * 100;
}

export default async function SiteAnalytics({
  params,
}: {
  params: Promise<{ siteId: string }>;
}) {
  const principal = await getPrincipal();
  if (!principal) redirect("/login");

  const { siteId } = await params;
  const q = <T,>(sql: string, args: unknown[] = []) =>
    tenantQuery<T>(principal.orgId, principal.role, sql, args);

  const [site] = await q<{
    site_id: string;
    domain: string;
    client_name: string;
    gsc_property: string | null;
    ga4_property_id: string | null;
  }>(
    `SELECT s.id AS site_id, s.domain, c.name AS client_name,
            s.gsc_property, s.ga4_property_id
     FROM   sites s JOIN clients c ON c.id = s.client_id
     WHERE  s.id = $1 AND s.deleted_at IS NULL`,
    [siteId],
  );

  // RLS already prevents reading another org's site; this turns the resulting
  // empty row into a 404 rather than a crash.
  if (!site) notFound();

  const [
    totals,
    trend,
    queries,
    pages,
    devices,
    countries,
    opportunities,
    ga4Totals,
    landingPages,
    channels,
  ] = await Promise.all([
    q<Row>(
      `SELECT
         sum(clicks)      FILTER (WHERE date >= current_date - $2::int) AS clicks,
         sum(impressions) FILTER (WHERE date >= current_date - $2::int) AS impressions,
         avg(position)    FILTER (WHERE date >= current_date - $2::int) AS position,
         sum(clicks)      FILTER (WHERE date >= current_date - ($2::int * 2)
                                    AND date <  current_date - $2::int) AS prev_clicks,
         sum(impressions) FILTER (WHERE date >= current_date - ($2::int * 2)
                                    AND date <  current_date - $2::int) AS prev_impressions,
         avg(position)    FILTER (WHERE date >= current_date - ($2::int * 2)
                                    AND date <  current_date - $2::int) AS prev_position
       FROM gsc_daily WHERE site_id = $1`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT date::text AS date, sum(clicks) AS clicks, sum(impressions) AS impressions
       FROM   gsc_daily
       WHERE  site_id = $1 AND date >= current_date - $2::int
       GROUP  BY date ORDER BY date`,
      [siteId, TREND_DAYS],
    ),
    q<Row>(
      `SELECT query,
              sum(clicks) AS clicks, sum(impressions) AS impressions,
              sum(clicks)::numeric / nullif(sum(impressions), 0) AS ctr,
              avg(position) AS position
       FROM   gsc_daily
       WHERE  site_id = $1 AND date >= current_date - $2::int AND query IS NOT NULL
       GROUP  BY query ORDER BY clicks DESC, impressions DESC LIMIT 25`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT page,
              sum(clicks) AS clicks, sum(impressions) AS impressions,
              sum(clicks)::numeric / nullif(sum(impressions), 0) AS ctr,
              avg(position) AS position
       FROM   gsc_daily
       WHERE  site_id = $1 AND date >= current_date - $2::int AND page IS NOT NULL
       GROUP  BY page ORDER BY clicks DESC, impressions DESC LIMIT 25`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT coalesce(device, 'unknown') AS device,
              sum(clicks) AS clicks, sum(impressions) AS impressions
       FROM   gsc_daily WHERE site_id = $1 AND date >= current_date - $2::int
       GROUP  BY device ORDER BY impressions DESC`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT coalesce(country, 'unknown') AS country,
              sum(clicks) AS clicks, sum(impressions) AS impressions
       FROM   gsc_daily WHERE site_id = $1 AND date >= current_date - $2::int
       GROUP  BY country ORDER BY impressions DESC LIMIT 8`,
      [siteId, WINDOW],
    ),
    // The opportunity view already exists in migration 0001 and nothing has
    // ever rendered it: queries ranking 5–20 with real impression volume, i.e.
    // page one is within reach without new content.
    q<Row>(
      `SELECT query, impressions, clicks, avg_position, ctr
       FROM   mv_query_opportunities
       WHERE  site_id = $1
       ORDER  BY impressions DESC LIMIT 20`,
      [siteId],
    ),
    q<Row>(
      `SELECT sum(sessions) AS sessions, sum(engaged_sessions) AS engaged,
              sum(conversions) AS conversions, sum(revenue) AS revenue,
              sum(sessions) FILTER (WHERE date >= current_date - ($2::int * 2)
                                      AND date <  current_date - $2::int) AS prev_sessions
       FROM   ga4_daily WHERE site_id = $1 AND date >= current_date - ($2::int * 2)`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT landing_page, sum(sessions) AS sessions,
              sum(conversions) AS conversions, sum(revenue) AS revenue
       FROM   ga4_daily
       WHERE  site_id = $1 AND date >= current_date - $2::int AND landing_page IS NOT NULL
       GROUP  BY landing_page ORDER BY sessions DESC LIMIT 15`,
      [siteId, WINDOW],
    ),
    q<Row>(
      `SELECT coalesce(channel, 'unknown') AS channel, sum(sessions) AS sessions
       FROM   ga4_daily WHERE site_id = $1 AND date >= current_date - $2::int
       GROUP  BY channel ORDER BY sessions DESC LIMIT 8`,
      [siteId, WINDOW],
    ),
  ]);

  const t = totals[0] ?? {};
  const clicks = n(t.clicks);
  const impressions = n(t.impressions);
  const position = t.position === null ? null : n(t.position);
  const prevPosition = t.prev_position === null ? null : n(t.prev_position);

  const clickTrend: TrendPoint[] = trend.map((r) => ({
    date: String(r.date),
    value: n(r.clicks),
  }));
  const imprTrend: TrendPoint[] = trend.map((r) => ({
    date: String(r.date),
    value: n(r.impressions),
  }));

  const deviceMax = Math.max(...devices.map((d) => n(d.impressions)), 1);
  const countryMax = Math.max(...countries.map((c) => n(c.impressions)), 1);
  const channelMax = Math.max(...channels.map((c) => n(c.sessions)), 1);

  const g = ga4Totals[0] ?? {};
  const hasGa4 = Boolean(site.ga4_property_id);

  const pct = (v: unknown) =>
    v === null || v === undefined ? "—" : `${(Number(v) * 100).toFixed(1)}%`;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 h-16 border-b border-line bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Link href="/" className="caption shrink-0 text-body hover:text-title">
              ← Dashboard
            </Link>
            <span className="truncate body-sm text-title">{site.client_name}</span>
            <span className="mono-label hidden truncate text-muted sm:inline">
              {site.domain}
            </span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] space-y-8 px-6 py-10">
        <div>
          <p className="mono-label uppercase text-muted">Last {WINDOW} days</p>
          <h1 className="subheading mt-2 text-title">{site.domain}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
              {site.gsc_property ? "Search Console connected" : "No Search Console"}
            </span>
            <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
              {hasGa4 ? "Analytics connected" : "No Analytics"}
            </span>
          </div>
        </div>

        {/* ── Headline figures ─────────────────────────────────────── */}
        <section className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-4">
          <Stat
            label="Clicks"
            value={clicks.toLocaleString()}
            delta={pctChange(clicks, n(t.prev_clicks))}
          />
          <Stat
            label="Impressions"
            value={impressions.toLocaleString()}
            delta={pctChange(impressions, n(t.prev_impressions))}
          />
          <Stat
            label="CTR"
            value={impressions ? `${((clicks / impressions) * 100).toFixed(2)}%` : "—"}
          />
          <div className="bg-surface px-5 py-4">
            <p className="mono-label uppercase text-muted">Avg position</p>
            <p
              className="tnum mt-2 text-title"
              style={{ fontSize: 24, fontWeight: 510, letterSpacing: "-0.012em" }}
            >
              {position === null ? "—" : position.toFixed(1)}
            </p>
            <p className="label tnum mt-1">
              <PositionDelta
                value={
                  position === null || prevPosition === null
                    ? null
                    : position - prevPosition
                }
              />
            </p>
          </div>
        </section>

        {/* ── Trend ──────────────────────────────────────────────────
            Two charts, one measure each. Never two y-axes. */}
        <Panel title="Trend" hint={`Daily, last ${TREND_DAYS} days`}>
          <div className="space-y-8">
            <TrendChart points={clickTrend} label="Clicks" />
            <TrendChart points={imprTrend} label="Impressions" />
          </div>
        </Panel>

        {/* ── Opportunities ───────────────────────────────────────── */}
        <Panel
          title="Opportunities"
          hint="Ranking 5–20 with volume — page one is reachable"
        >
          <DataTable
            rows={opportunities}
            empty="No queries in the 5–20 band with enough impressions yet. This fills in as the property accumulates data."
            columns={[
              { key: "q", header: "Query", truncate: true, render: (r) => <span className="text-title">{String(r.query)}</span> },
              { key: "i", header: "Impressions", align: "right", render: (r) => n(r.impressions).toLocaleString() },
              { key: "c", header: "Clicks", align: "right", render: (r) => n(r.clicks).toLocaleString() },
              { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
              { key: "p", header: "Position", align: "right", render: (r) => n(r.avg_position).toFixed(1) },
            ]}
          />
        </Panel>

        {/* ── Query & page explorers ──────────────────────────────── */}
        <div className="grid gap-8 lg:grid-cols-2">
          <Panel title="Top queries" hint="By clicks">
            <DataTable
              rows={queries}
              empty="No query data in this window."
              columns={[
                { key: "q", header: "Query", truncate: true, render: (r) => <span className="text-title">{String(r.query)}</span> },
                { key: "c", header: "Clicks", align: "right", render: (r) => n(r.clicks).toLocaleString() },
                { key: "i", header: "Impr.", align: "right", render: (r) => n(r.impressions).toLocaleString() },
                { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
                { key: "p", header: "Pos.", align: "right", render: (r) => n(r.position).toFixed(1) },
              ]}
            />
          </Panel>

          <Panel title="Top pages" hint="By clicks">
            <DataTable
              rows={pages}
              empty="No page data in this window."
              columns={[
                {
                  key: "p",
                  header: "Page",
                  truncate: true,
                  render: (r) => (
                    <span className="text-title" title={String(r.page)}>
                      {String(r.page).replace(/^https?:\/\/[^/]+/, "") || "/"}
                    </span>
                  ),
                },
                { key: "c", header: "Clicks", align: "right", render: (r) => n(r.clicks).toLocaleString() },
                { key: "i", header: "Impr.", align: "right", render: (r) => n(r.impressions).toLocaleString() },
                { key: "ctr", header: "CTR", align: "right", render: (r) => pct(r.ctr) },
              ]}
            />
          </Panel>
        </div>

        {/* ── Breakdowns ──────────────────────────────────────────── */}
        <div className="grid gap-8 lg:grid-cols-2">
          <Panel title="Devices" hint="By impressions">
            {devices.length === 0 ? (
              <Empty>No device data in this window.</Empty>
            ) : (
              devices.map((d) => (
                <BarRow
                  key={String(d.device)}
                  label={String(d.device)}
                  value={n(d.impressions)}
                  max={deviceMax}
                  secondary={`${n(d.clicks).toLocaleString()} clicks`}
                />
              ))
            )}
          </Panel>

          <Panel title="Countries" hint="By impressions">
            {countries.length === 0 ? (
              <Empty>No country data in this window.</Empty>
            ) : (
              countries.map((c) => (
                <BarRow
                  key={String(c.country)}
                  label={String(c.country).toUpperCase()}
                  value={n(c.impressions)}
                  max={countryMax}
                  secondary={`${n(c.clicks).toLocaleString()} clicks`}
                />
              ))
            )}
          </Panel>
        </div>

        {/* ── Analytics ───────────────────────────────────────────── */}
        <Panel
          title="Analytics"
          hint={hasGa4 ? `Last ${WINDOW} days` : "Not connected"}
        >
          {!hasGa4 ? (
            <Empty>
              No Google Analytics property is connected for this site.{" "}
              <Link href="/connect" className="text-body underline underline-offset-2 hover:text-title">
                Connect one
              </Link>
              .
            </Empty>
          ) : (
            <div className="space-y-8">
              <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-line bg-line md:grid-cols-4">
                <Stat
                  label="Sessions"
                  value={n(g.sessions).toLocaleString()}
                  delta={pctChange(n(g.sessions), n(g.prev_sessions))}
                />
                <Stat label="Engaged" value={n(g.engaged).toLocaleString()} />
                <Stat label="Conversions" value={n(g.conversions).toLocaleString()} />
                <Stat
                  label="Revenue"
                  value={n(g.revenue).toLocaleString(undefined, {
                    maximumFractionDigits: 0,
                  })}
                />
              </div>

              <div className="grid gap-8 lg:grid-cols-2">
                <div>
                  <p className="mono-label mb-3 uppercase text-muted">
                    Top landing pages
                  </p>
                  <DataTable
                    rows={landingPages}
                    empty="No landing-page data in this window."
                    columns={[
                      {
                        key: "lp",
                        header: "Landing page",
                        truncate: true,
                        render: (r) => (
                          <span className="text-title">{String(r.landing_page)}</span>
                        ),
                      },
                      { key: "s", header: "Sessions", align: "right", render: (r) => n(r.sessions).toLocaleString() },
                      { key: "c", header: "Conv.", align: "right", render: (r) => n(r.conversions).toLocaleString() },
                    ]}
                  />
                </div>
                <div>
                  <p className="mono-label mb-3 uppercase text-muted">Channels</p>
                  {channels.length === 0 ? (
                    <Empty>No channel data in this window.</Empty>
                  ) : (
                    channels.map((c) => (
                      <BarRow
                        key={String(c.channel)}
                        label={String(c.channel)}
                        value={n(c.sessions)}
                        max={channelMax}
                      />
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </Panel>

        {/* Correlation, not causation — CLAUDE.md rule 7. This screen shows
            what happened; it deliberately never asserts why. */}
        <p className="body-sm text-muted">
          Figures come from Google Search Console and Google Analytics, refreshed
          nightly. Where two things moved together, this screen reports that they
          moved together — it does not claim one caused the other.
        </p>
      </main>
    </div>
  );
}
