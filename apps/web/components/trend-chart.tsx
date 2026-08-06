"use client";

import { useId, useState } from "react";

export type TrendPoint = { date: string; value: number };

/**
 * A single-series daily trend.
 *
 * Deliberately ONE measure per chart. Clicks and impressions differ by roughly
 * fifty times on a typical property, so plotting both against two y-axes would
 * let the visual crossing points mean whatever the scales happened to make
 * them. Two stacked charts sharing an x-range say the same thing without
 * inventing a relationship.
 *
 * No legend: with one series the heading names it, and a legend box would be
 * chrome for nothing.
 *
 * Colour comes from --color-chart-1, which is a validated step per theme and
 * is NOT the acid-lime accent — DESIGN.md reserves that for the single primary
 * action on a view, and a data line is not an action.
 */
export function TrendChart({
  points,
  label,
  format = (n: number) => n.toLocaleString(),
}: {
  points: TrendPoint[];
  label: string;
  format?: (n: number) => string;
}) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  if (points.length === 0) {
    return (
      <div className="flex h-[180px] items-center justify-center rounded-md border border-line">
        <p className="body-sm text-muted">No data for this period.</p>
      </div>
    );
  }

  const W = 720;
  const H = 180;
  const PAD_X = 8;
  const PAD_TOP = 12;
  const PAD_BOTTOM = 24;

  const max = Math.max(...points.map((p) => p.value), 1);
  const plotH = H - PAD_TOP - PAD_BOTTOM;
  const stepX =
    points.length > 1 ? (W - PAD_X * 2) / (points.length - 1) : 0;

  const x = (i: number) => PAD_X + i * stepX;
  const y = (v: number) => PAD_TOP + plotH - (v / max) * plotH;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.value)}`).join(" ");
  const area =
    `${line} L${x(points.length - 1)},${PAD_TOP + plotH} L${x(0)},${PAD_TOP + plotH} Z`;

  const active = hover === null ? null : points[hover];

  return (
    <div className="relative">
      <div className="flex items-baseline justify-between">
        <p className="mono-label uppercase text-muted">{label}</p>
        {/* The hovered value replaces the total, so the number the eye is
            already on is the one that updates — no second place to look. */}
        <p className="caption tnum text-title">
          {active
            ? `${format(active.value)} · ${new Date(active.date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}`
            : `${format(points.reduce((a, p) => a + p.value, 0))} total`}
        </p>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="mt-3 w-full"
        style={{ height: H }}
        role="img"
        aria-label={`${label} by day. Highest ${format(max)}.`}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity="0.18" />
            <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Recessive grid — three lines, no axis box. */}
        {[0, 0.5, 1].map((t) => (
          <line
            key={t}
            x1={PAD_X}
            x2={W - PAD_X}
            y1={PAD_TOP + plotH * t}
            y2={PAD_TOP + plotH * t}
            stroke="var(--color-chart-grid)"
            strokeWidth="1"
          />
        ))}

        <path d={area} fill={`url(#${gradientId})`} />
        <path
          d={line}
          fill="none"
          stroke="var(--color-chart-1)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {active && hover !== null && (
          <>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD_TOP}
              y2={PAD_TOP + plotH}
              stroke="var(--color-chart-1)"
              strokeWidth="1"
              strokeOpacity="0.5"
            />
            {/* 2px surface ring so the marker reads against the line beneath. */}
            <circle
              cx={x(hover)}
              cy={y(active.value)}
              r="4"
              fill="var(--color-chart-1)"
              stroke="var(--color-canvas)"
              strokeWidth="2"
            />
          </>
        )}

        {/* Hit targets are full-height bands, much wider than the marks —
            pointing at a 2px line is not a reasonable thing to ask. */}
        {points.map((p, i) => (
          <rect
            key={p.date}
            x={x(i) - stepX / 2}
            y={PAD_TOP}
            width={Math.max(stepX, 4)}
            height={plotH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}

        {/* Endpoints only. A date on every tick is unreadable at 90 points. */}
        <text x={PAD_X} y={H - 6} className="fill-[var(--color-muted)]" fontSize="11">
          {new Date(points[0].date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
        </text>
        <text
          x={W - PAD_X}
          y={H - 6}
          textAnchor="end"
          className="fill-[var(--color-muted)]"
          fontSize="11"
        >
          {new Date(points[points.length - 1].date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}
        </text>
      </svg>
    </div>
  );
}
