import { MarketingHome } from "@/components/marketing-home";
import { tenantQuery } from "@/lib/db";
import { getPrincipal } from "@/lib/session";

export const dynamic = "force-dynamic";

type SiteRow = {
  site_id: string;
  domain: string;
  client_name: string;
  clicks_28d: string;
  clicks_prev_28d: string;
  impressions_28d: string;
  avg_position_28d: string | null;
  critical_issues: string;
};

function pctChange(now: number, prev: number): number | null {
  if (!prev) return null;
  return ((now - prev) / prev) * 100;
}

function Delta({ value }: { value: number | null }) {
  if (value === null) return <span className="text-mute">—</span>;
  const up = value >= 0;
  return (
    <span className={up ? "text-cyan-deep" : "text-error"}>
      {up ? "↑" : "↓"} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export default async function Dashboard() {
  const principal = await getPrincipal();
  // A logged-out visitor gets the public homepage rather than a bounce to
  // /login. Google's OAuth verification requires the homepage on the verified
  // domain to be reachable without signing in — a redirect to a sign-in wall
  // is a documented rejection reason.
  if (!principal) return <MarketingHome />;

  // RSC reads Postgres directly through a tenant-scoped transaction, off the
  // materialised view — never live aggregation. docs/04-ui-ux.md §11.
  const sites = await tenantQuery<SiteRow>(
    principal.orgId,
    principal.role,
    `SELECT s.id AS site_id, s.domain, c.name AS client_name,
            COALESCE(k.clicks_28d, 0)        AS clicks_28d,
            COALESCE(k.clicks_prev_28d, 0)   AS clicks_prev_28d,
            COALESCE(k.impressions_28d, 0)   AS impressions_28d,
            k.avg_position_28d,
            (SELECT count(*) FROM issues i
              WHERE i.site_id = s.id AND i.state = 'open'
                AND i.severity = 'critical') AS critical_issues
     FROM   sites s
     JOIN   clients c         ON c.id = s.client_id
     LEFT JOIN mv_site_kpis k ON k.site_id = s.id
     WHERE  s.deleted_at IS NULL AND c.deleted_at IS NULL
     ORDER BY critical_issues DESC, clicks_28d DESC`,
  );

  const totalClicks = sites.reduce((a, s) => a + Number(s.clicks_28d), 0);
  const totalPrev = sites.reduce((a, s) => a + Number(s.clicks_prev_28d), 0);
  const totalImpr = sites.reduce((a, s) => a + Number(s.impressions_28d), 0);
  const totalIssues = sites.reduce((a, s) => a + Number(s.critical_issues), 0);
  const clients = new Set(sites.map((s) => s.client_name)).size;

  const attention = sites.filter((s) => Number(s.critical_issues) > 0);
  const healthy = sites.filter((s) => Number(s.critical_issues) === 0);

  return (
    <div className="min-h-screen">
      {/* Nav bar: 64px, canvas, hairline base — DESIGN.md nav-bar */}
      <header className="sticky top-0 z-10 h-16 border-b border-hairline bg-canvas/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-6 w-6 items-center justify-center rounded-xs bg-primary">
              <span className="caption-mono text-on-primary">S</span>
            </div>
            <span className="body-sm-strong text-ink">{principal.orgName}</span>
            <span className="caption-mono rounded-full bg-canvas-soft-2 px-2 py-0.5 text-mute">
              {principal.role}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="/connect"
              className="body-sm-strong flex h-7 items-center rounded-sm bg-primary px-2.5 text-on-primary transition-opacity hover:opacity-90"
            >
              Connect a site
            </a>
            <span className="body-sm hidden text-body sm:inline">{principal.email}</span>
            <form action={`${process.env.API_URL}/v1/auth/logout`} method="post">
              {/* nav-cta: 28px, 6px radius */}
              <button className="body-sm-strong h-7 rounded-sm border border-hairline bg-canvas px-2 text-ink transition-colors hover:bg-canvas-soft-2">
                Sign out
              </button>
            </form>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-12">
        {sites.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="mb-10">
              <p className="caption-mono mb-3 uppercase text-mute">Overview</p>
              <h1 className="display-lg text-ink">
                {clients} client{clients === 1 ? "" : "s"}, {sites.length} site
                {sites.length === 1 ? "" : "s"}.
              </h1>
              <p className="body-md mt-2 text-body">
                Search Console and Analytics for the last 28 days.
              </p>
            </div>

            {/* Stat row — card-soft chrome */}
            <section className="mb-12 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-hairline bg-hairline md:grid-cols-4">
              <Stat label="Clicks" value={totalClicks.toLocaleString()}>
                <Delta value={pctChange(totalClicks, totalPrev)} />
              </Stat>
              <Stat label="Impressions" value={totalImpr.toLocaleString()} />
              <Stat
                label="Avg CTR"
                value={totalImpr ? `${((totalClicks / totalImpr) * 100).toFixed(1)}%` : "—"}
              />
              <Stat
                label="Critical issues"
                value={String(totalIssues)}
                tone={totalIssues > 0 ? "error" : undefined}
              />
            </section>

            {attention.length > 0 && (
              <section className="mb-12">
                <p className="caption-mono mb-4 uppercase text-mute">Needs attention</p>
                <div className="grid gap-4 md:grid-cols-2">
                  {attention.map((s) => (
                    <SiteCard key={s.site_id} site={s} />
                  ))}
                </div>
              </section>
            )}

            {healthy.length > 0 && (
              <section className="mb-12">
                <p className="caption-mono mb-4 uppercase text-mute">Healthy</p>
                <div className="overflow-hidden rounded-md border border-hairline bg-canvas">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-hairline bg-canvas-soft">
                        <th className="caption-mono px-4 py-2.5 text-left uppercase text-mute">
                          Client
                        </th>
                        <th className="caption-mono px-4 py-2.5 text-left uppercase text-mute">
                          Domain
                        </th>
                        <th className="caption-mono px-4 py-2.5 text-right uppercase text-mute">
                          Clicks
                        </th>
                        <th className="caption-mono px-4 py-2.5 text-right uppercase text-mute">
                          28d
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {healthy.map((s, i) => (
                        <tr
                          key={s.site_id}
                          className={i > 0 ? "border-t border-hairline" : ""}
                        >
                          <td className="body-sm-strong px-4 py-3 text-ink">
                            {s.client_name}
                          </td>
                          <td className="body-sm px-4 py-3 text-body">{s.domain}</td>
                          <td className="body-sm tnum px-4 py-3 text-right text-ink">
                            {Number(s.clicks_28d).toLocaleString()}
                          </td>
                          <td className="body-sm tnum px-4 py-3 text-right">
                            <Delta
                              value={pctChange(
                                Number(s.clicks_28d),
                                Number(s.clicks_prev_28d),
                              )}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <footer className="border-t border-hairline pt-6">
              <p className="body-sm text-mute">
                Phase 0 — schema, tenancy, row-level security, and authentication
                are live. Search Console sync, the technical scanner, and AI
                reporting are Phase 1.
              </p>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  children,
}: {
  label: string;
  value: string;
  tone?: "error";
  children?: React.ReactNode;
}) {
  return (
    <div className="bg-canvas px-5 py-4">
      <p className="caption-mono uppercase text-mute">{label}</p>
      <p
        className={`display-md tnum mt-2 ${tone === "error" ? "text-error" : "text-ink"}`}
      >
        {value}
      </p>
      {children && <p className="body-sm tnum mt-1">{children}</p>}
    </div>
  );
}

function SiteCard({ site }: { site: SiteRow }) {
  const change = pctChange(Number(site.clicks_28d), Number(site.clicks_prev_28d));
  return (
    <article className="elevate-1 rounded-md border border-hairline bg-canvas p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="display-sm truncate text-ink">{site.client_name}</h2>
          <p className="caption-mono mt-1 truncate text-mute">{site.domain}</p>
        </div>
        <span className="caption-mono shrink-0 rounded-full bg-error-soft px-2 py-1 text-error-deep">
          {site.critical_issues} critical
        </span>
      </div>

      <dl className="mt-6 grid grid-cols-3 gap-4">
        <div>
          <dt className="caption-mono uppercase text-mute">Clicks</dt>
          <dd className="body-md tnum mt-1 text-ink">
            {Number(site.clicks_28d).toLocaleString()}
          </dd>
          <dd className="body-sm tnum">
            <Delta value={change} />
          </dd>
        </div>
        <div>
          <dt className="caption-mono uppercase text-mute">Impressions</dt>
          <dd className="body-md tnum mt-1 text-ink">
            {Number(site.impressions_28d).toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="caption-mono uppercase text-mute">Avg pos</dt>
          <dd className="body-md tnum mt-1 text-ink">
            {site.avg_position_28d ? Number(site.avg_position_28d).toFixed(1) : "—"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="rounded-md border border-hairline bg-canvas px-8 py-20 text-center">
      <h2 className="display-md text-ink">No clients yet.</h2>
      <p className="body-md mx-auto mt-3 max-w-md text-body">
        Phase 0 is complete — authentication, tenancy, and the full schema are
        live. Connecting Search Console is Phase 1.
      </p>
      <a
        href="/connect"
        className="elevate-1 mt-8 inline-flex h-10 items-center rounded-sm bg-primary px-4 text-on-primary transition-opacity hover:opacity-90"
      >
        <span className="body-sm-strong">Connect Search Console</span>
      </a>
      <p className="body-sm mx-auto mt-6 max-w-md text-mute">
        Or load sample data with{" "}
        <code className="caption-mono rounded-xs bg-canvas-soft-2 px-1.5 py-0.5 text-ink">
          uv run python scripts/seed_demo.py
        </code>
      </p>
    </div>
  );
}
