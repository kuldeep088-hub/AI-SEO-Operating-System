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

/**
 * DESIGN.md is in slight tension with itself here: the colour table calls
 * pulse-green and coral-red "supporting accent, not a status color", while the
 * Agent Prompt Guide sanctions "#27a644 for success, #eb5757 for error" on
 * badges. A directional metric with no colour is materially worse to read, so
 * this follows the Prompt Guide — and pairs colour with an arrow glyph so the
 * direction survives for anyone who cannot distinguish the two hues.
 */
function Delta({ value }: { value: number | null }) {
  if (value === null) return <span className="text-ash">—</span>;
  const up = value >= 0;
  return (
    <span className={up ? "text-pulse-green" : "text-coral-red"}>
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
      {/* Fixed top bar, left logo, right links, no sidebar — DESIGN.md §Layout. */}
      <header className="sticky top-0 z-10 h-16 border-b border-graphite bg-void/80 backdrop-blur-md">
        <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            {/* The logo mark is a white glyph, not a lime chip. Acid lime is
                reserved for the one primary action per view — here that is
                "Connect a site" — and spending it on branding would leave the
                actual CTA with nothing to distinguish it. */}
            <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
              <path
                d="M2 9.5 L9 2.5 L16 9.5 L9 16.5 Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-paper"
              />
            </svg>
            <span className="body-sm text-paper">{principal.orgName}</span>
            <span className="label rounded-sm bg-white/5 px-1.5 py-0.5 text-fog">
              {principal.role}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="caption hidden text-ash sm:inline">
              {principal.email}
            </span>
            <form action={`${process.env.API_URL}/v1/auth/logout`} method="post">
              <button className="caption h-8 rounded-md border border-graphite px-3 text-mist transition-colors hover:border-smoke hover:text-paper">
                Sign out
              </button>
            </form>
            {/* Neutral white pill, not lime. On an empty dashboard the
                EmptyState already owns the one acid-lime action; two would
                break the rule that exactly one primary action exists per view.
                DESIGN.md's "Sign-up Button (Rounded Pill, Neutral)" is the
                intended second-highest-contrast element for exactly this. */}
            <a
              href="/connect"
              className="flex h-8 items-center rounded-full bg-paper px-4 text-void transition-opacity hover:opacity-90"
              style={{ fontSize: 13, fontWeight: 510, letterSpacing: "-0.011em" }}
            >
              Connect a site
            </a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1200px] px-6 py-12">
        {sites.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="mb-10">
              <p className="mono-label mb-3 uppercase text-ash">Overview</p>
              <h1 className="subheading text-paper">
                {clients} client{clients === 1 ? "" : "s"}, {sites.length} site
                {sites.length === 1 ? "" : "s"}.
              </h1>
              <p className="body-base mt-2 text-fog">
                Search Console and Analytics for the last 28 days.
              </p>
            </div>

            {/* Stat row — card-soft chrome */}
            <section className="mb-12 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-graphite bg-graphite md:grid-cols-4">
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
                <p className="mono-label mb-4 uppercase text-ash">Needs attention</p>
                <div className="grid gap-4 md:grid-cols-2">
                  {attention.map((s) => (
                    <SiteCard key={s.site_id} site={s} />
                  ))}
                </div>
              </section>
            )}

            {healthy.length > 0 && (
              <section className="mb-12">
                <p className="mono-label mb-4 uppercase text-ash">Healthy</p>
                <div className="overflow-hidden rounded-lg border border-graphite bg-carbon">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-graphite bg-obsidian">
                        <th className="mono-label px-4 py-2.5 text-left uppercase text-ash">
                          Client
                        </th>
                        <th className="mono-label px-4 py-2.5 text-left uppercase text-ash">
                          Domain
                        </th>
                        <th className="mono-label px-4 py-2.5 text-right uppercase text-ash">
                          Clicks
                        </th>
                        <th className="mono-label px-4 py-2.5 text-right uppercase text-ash">
                          28d
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {healthy.map((s, i) => (
                        <tr
                          key={s.site_id}
                          className={i > 0 ? "border-t border-graphite" : ""}
                        >
                          <td className="body-sm px-4 py-3 text-paper">
                            {s.client_name}
                          </td>
                          <td className="body-sm px-4 py-3 text-fog">{s.domain}</td>
                          <td className="body-sm tnum px-4 py-3 text-right text-paper">
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

            <footer className="border-t border-graphite pt-6">
              <p className="body-sm text-ash">
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
    <div className="bg-carbon px-5 py-4">
      <p className="mono-label uppercase text-ash">{label}</p>
      <p
        className={`heading tnum mt-2 ${tone === "error" ? "text-coral-red" : "text-paper"}`}
      >
        {value}
      </p>
      {children && <p className="body-sm tnum mt-1">{children}</p>}
    </div>
  );
}

function SiteCard({ site }: { site: SiteRow }) {
  const change = pctChange(Number(site.clicks_28d), Number(site.clicks_prev_28d));
  // `card` already supplies the carbon fill, 12px radius and hairline inset
  // ring — DESIGN.md says cards get a border, not a drop shadow.
  return (
    <article className="card p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="body-emphasis truncate text-paper">{site.client_name}</h2>
          <p className="mono-label mt-1 truncate text-ash">{site.domain}</p>
        </div>
        <span className="label shrink-0 rounded-sm bg-coral-red/10 px-1.5 py-0.5 text-coral-red">
          {site.critical_issues} critical
        </span>
      </div>

      <dl className="mt-6 grid grid-cols-3 gap-4">
        <div>
          <dt className="mono-label uppercase text-ash">Clicks</dt>
          <dd className="body-base tnum mt-1 text-paper">
            {Number(site.clicks_28d).toLocaleString()}
          </dd>
          <dd className="body-sm tnum">
            <Delta value={change} />
          </dd>
        </div>
        <div>
          <dt className="mono-label uppercase text-ash">Impressions</dt>
          <dd className="body-base tnum mt-1 text-paper">
            {Number(site.impressions_28d).toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="mono-label uppercase text-ash">Avg pos</dt>
          <dd className="body-base tnum mt-1 text-paper">
            {site.avg_position_28d ? Number(site.avg_position_28d).toFixed(1) : "—"}
          </dd>
        </div>
      </dl>
    </article>
  );
}

function EmptyState() {
  return (
    <div className="card px-8 py-20 text-center">
      <h2 className="heading text-paper">No clients yet.</h2>
      <p className="body-sm mx-auto mt-3 max-w-md text-fog">
        Phase 0 is complete — authentication, tenancy, and the full schema are
        live. Connecting Search Console is Phase 1.
      </p>
      <a
        href="/connect"
        className="mt-8 inline-flex h-10 items-center rounded-md bg-acid-lime px-4 text-void transition-opacity hover:opacity-90"
        style={{ fontSize: 14, fontWeight: 510, letterSpacing: "-0.011em" }}
      >
        Connect Search Console
      </a>
      <p className="body-sm mx-auto mt-6 max-w-md text-ash">
        Or load sample data with{" "}
        <code className="mono-label rounded-sm bg-white/5 px-1.5 py-0.5 text-mist">
          uv run python scripts/seed_demo.py
        </code>
      </p>
    </div>
  );
}
