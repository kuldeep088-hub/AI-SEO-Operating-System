/**
 * The hero's product frame.
 *
 * DESIGN.md §Imagery is emphatic that this brand's visual language is
 * "product-screenshot-first … real app UI captured at full fidelity … No stock
 * photography, no lifestyle imagery, no abstract illustration." Rather than
 * ship a screenshot that goes stale the first time the dashboard changes, this
 * renders the same shapes the real dashboard renders, from the same tokens.
 *
 * The numbers are illustrative and the frame says so — a marketing page that
 * shows invented metrics without labelling them is the kind of thing a Google
 * reviewer reasonably treats as misleading.
 */

const ROWS = [
  { client: "Northwind Retail", domain: "northwind.example", clicks: "18,204", delta: 12.4 },
  { client: "Helio Health", domain: "heliohealth.example", clicks: "9,876", delta: 4.1 },
  { client: "Atlas Logistics", domain: "atlas.example", clicks: "6,530", delta: -2.8 },
];

function Delta({ value }: { value: number }) {
  const up = value >= 0;
  return (
    <span className={up ? "text-positive" : "text-negative"}>
      {up ? "↑" : "↓"} {Math.abs(value).toFixed(1)}%
    </span>
  );
}

export function ProductPreview() {
  return (
    <div className="relative">
      {/* Hero Gradient Floor — the only gradient the system permits, and it
          sits under the frame rather than on any component. */}
      <div
        aria-hidden="true"
        className="gradient-floor pointer-events-none absolute inset-x-0 bottom-0 h-40 opacity-20"
      />

      <div className="card relative p-6">
        {/* Window chrome, mirroring the real app's nav proportions. */}
        <div className="flex items-center justify-between border-b border-line pb-4">
          <div className="flex items-center gap-2.5">
            <svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true">
              <path
                d="M2 9.5 L9 2.5 L16 9.5 L9 16.5 Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className="text-title"
              />
            </svg>
            <span className="caption text-title">Acme Agency</span>
            <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-subtle">
              owner
            </span>
          </div>
          <span className="label rounded-sm bg-fill-subtle px-1.5 py-0.5 text-muted">
            illustrative data
          </span>
        </div>

        {/* Stat row — same four measures as the real dashboard. */}
        <div className="mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line md:grid-cols-4">
          {[
            { label: "Clicks", value: "34,610", delta: 8.2 },
            { label: "Impressions", value: "912,447" },
            { label: "Avg CTR", value: "3.8%" },
            { label: "Critical issues", value: "2", bad: true },
          ].map((s) => (
            <div key={s.label} className="bg-surface px-4 py-3">
              <p className="mono-label uppercase text-muted">{s.label}</p>
              <p
                className={`tnum mt-1.5 ${s.bad ? "text-negative" : "text-title"}`}
                style={{ fontSize: 20, fontWeight: 510, letterSpacing: "-0.012em" }}
              >
                {s.value}
              </p>
              {s.delta !== undefined && (
                <p className="label tnum mt-0.5">
                  <Delta value={s.delta} />
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Site table — same columns as the real dashboard's "Healthy" table. */}
        <div className="mt-4 overflow-hidden rounded-md border border-line">
          <table className="w-full">
            <thead>
              <tr className="border-b border-line bg-surface-2">
                {["Client", "Domain", "Clicks", "28d"].map((h, i) => (
                  <th
                    key={h}
                    className={`mono-label px-4 py-2 uppercase text-muted ${
                      i > 1 ? "text-right" : "text-left"
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r, i) => (
                <tr
                  key={r.domain}
                  className={`bg-surface ${i > 0 ? "border-t border-line" : ""}`}
                >
                  <td className="caption px-4 py-2.5 text-title">{r.client}</td>
                  <td className="caption px-4 py-2.5 text-subtle">{r.domain}</td>
                  <td className="caption tnum px-4 py-2.5 text-right text-title">
                    {r.clicks}
                  </td>
                  <td className="caption tnum px-4 py-2.5 text-right">
                    <Delta value={r.delta} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
