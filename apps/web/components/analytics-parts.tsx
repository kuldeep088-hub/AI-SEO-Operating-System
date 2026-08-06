/**
 * Building blocks for the site analytics screen.
 *
 * Magnitude comparisons use bar length against a shared maximum, in one hue.
 * Giving each row its own colour would be a categorical encoding of something
 * that has no categories — the labels already carry identity, and it would
 * force an eight-hue palette that the CVD check has no reason to pass.
 */

export function Panel({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="body-lg text-title">{title}</h2>
        {hint && <p className="caption text-muted">{hint}</p>}
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="body-sm py-6 text-muted">{children}</p>;
}

/** A labelled magnitude row — used for devices, countries and channels. */
export function BarRow({
  label,
  value,
  max,
  suffix,
  secondary,
}: {
  label: string;
  value: number;
  max: number;
  suffix?: string;
  secondary?: string;
}) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  return (
    <div className="py-2">
      <div className="flex items-baseline justify-between gap-4">
        <span className="body-sm truncate text-body">{label}</span>
        <span className="caption tnum shrink-0 text-title">
          {value.toLocaleString()}
          {suffix}
          {secondary && <span className="ml-2 text-muted">{secondary}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-fill-subtle">
        <div
          className="h-full rounded-full bg-chart-1"
          style={{ width: `${Math.max(pct, 1)}%` }}
        />
      </div>
    </div>
  );
}

export type Column<T> = {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => React.ReactNode;
  /** Long free text (queries, URLs) needs to truncate rather than wrap. */
  truncate?: boolean;
};

export function DataTable<T>({
  rows,
  columns,
  empty,
}: {
  rows: T[];
  columns: Column<T>[];
  empty: string;
}) {
  if (rows.length === 0) return <Empty>{empty}</Empty>;
  return (
    // Wide tables scroll inside their own container so the page body never
    // scrolls horizontally on a phone.
    <div className="-mx-2 overflow-x-auto">
      <table className="w-full min-w-[520px]">
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th
                key={c.key}
                className={`mono-label px-2 pb-2 uppercase text-muted ${
                  c.align === "right" ? "text-right" : "text-left"
                }`}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={i > 0 ? "border-t border-line" : ""}>
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={`caption px-2 py-2.5 ${
                    c.align === "right" ? "tnum text-right" : "text-left"
                  } ${c.truncate ? "max-w-[260px] truncate" : ""}`}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A single headline figure with its previous-period comparison. */
export function Stat({
  label,
  value,
  delta,
  tone,
}: {
  label: string;
  value: string;
  delta?: number | null;
  tone?: "negative";
}) {
  return (
    <div className="bg-surface px-5 py-4">
      <p className="mono-label uppercase text-muted">{label}</p>
      <p
        className={`tnum mt-2 ${tone === "negative" ? "text-negative" : "text-title"}`}
        style={{ fontSize: 24, fontWeight: 510, letterSpacing: "-0.012em" }}
      >
        {value}
      </p>
      {delta !== undefined && (
        <p className="label tnum mt-1">
          <Delta value={delta} />
        </p>
      )}
    </div>
  );
}

/**
 * Direction is carried by an arrow as well as colour, so the comparison
 * survives for anyone who cannot separate the two hues.
 */
export function Delta({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">no prior period</span>;
  const up = value >= 0;
  return (
    <span className={up ? "text-positive" : "text-negative"}>
      {up ? "↑" : "↓"} {Math.abs(value).toFixed(1)}% vs prev 28d
    </span>
  );
}

/**
 * Average position improves as it falls, so the arrow and the colour both have
 * to invert. Every SEO tool that forgets this shows a "drop" in green.
 */
export function PositionDelta({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted">no prior period</span>;
  const improved = value <= 0;
  return (
    <span className={improved ? "text-positive" : "text-negative"}>
      {improved ? "↑" : "↓"} {Math.abs(value).toFixed(1)} vs prev 28d
    </span>
  );
}
