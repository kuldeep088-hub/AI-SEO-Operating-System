"use client";

import { useEffect, useState } from "react";

/**
 * Live backfill progress — docs/12-roadmap.md Phase 1 week 4.
 *
 * Connecting a site enqueues a 16-month Search Console backfill. The handler
 * has always reported progress into `jobs.progress`; nothing carried it to the
 * browser, so the user pressed Connect and then watched a static page for
 * several minutes with no way to tell the difference between "working" and
 * "broken".
 *
 * EventSource rather than polling: the browser handles reconnection itself,
 * and the server pushes only on change, so a backfill sitting at 40% for a
 * minute sends one frame rather than forty.
 */

type Job = {
  id: string;
  kind: string;
  status: string;
  pct: number | null;
  detail: string | null;
  error: string | null;
};

const LABELS: Record<string, string> = {
  gsc_backfill: "Search Console history",
  gsc_sync: "Search Console sync",
  ga4_backfill: "Analytics history",
  ga4_sync: "Analytics sync",
  refresh_views: "Updating dashboards",
  monthly_report: "Writing the monthly report",
};

const TERMINAL = new Set(["succeeded", "failed", "dead", "cancelled"]);

export function JobProgress({
  siteId,
  apiUrl,
}: {
  siteId: string;
  apiUrl: string;
}) {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [closed, setClosed] = useState(false);

  useEffect(() => {
    // withCredentials so the session cookie is sent: the API is a different
    // origin in development (:8000 vs :3000), and the stream is tenant-scoped.
    const source = new EventSource(`${apiUrl}/v1/jobs/stream/${siteId}`, {
      withCredentials: true,
    });

    source.addEventListener("jobs", (e) => {
      try {
        setJobs(JSON.parse((e as MessageEvent).data).jobs);
      } catch {
        // A malformed frame should not blank a working panel.
      }
    });
    source.addEventListener("done", () => {
      setClosed(true);
      source.close();
    });
    source.addEventListener("timeout", () => {
      setClosed(true);
      source.close();
    });
    source.onerror = () => {
      // EventSource reconnects on its own; closing here would defeat that.
      // Only a `done` or `timeout` event ends the stream deliberately.
    };

    return () => source.close();
  }, [siteId, apiUrl]);

  if (!jobs) {
    return (
      <p className="body-sm text-muted">Checking for running jobs…</p>
    );
  }
  if (jobs.length === 0) {
    return <p className="body-sm text-muted">No recent jobs for this site.</p>;
  }

  return (
    <div className="space-y-4">
      {jobs.map((job) => {
        const done = TERMINAL.has(job.status);
        const failed = job.status === "failed" || job.status === "dead";
        const pct = failed ? 100 : done ? 100 : (job.pct ?? 0);
        return (
          <div key={job.id}>
            <div className="flex items-baseline justify-between gap-4">
              <span className="body-sm text-title">
                {LABELS[job.kind] ?? job.kind}
              </span>
              <span
                className={`caption tnum ${failed ? "text-negative" : done ? "text-positive" : "text-subtle"}`}
              >
                {failed ? "failed" : done ? "done" : `${pct}%`}
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-fill-subtle">
              <div
                className={`h-full rounded-full transition-[width] duration-500 ${failed ? "bg-negative" : done ? "bg-positive" : "bg-chart-1"}`}
                style={{ width: `${Math.max(pct, 2)}%` }}
              />
            </div>
            {(job.detail || job.error) && (
              <p
                className={`caption mt-1.5 ${job.error ? "text-negative" : "text-muted"}`}
              >
                {job.error ?? job.detail}
              </p>
            )}
          </div>
        );
      })}
      {closed && (
        <p className="caption text-muted">
          {jobs.every((j) => TERMINAL.has(j.status))
            ? "All finished. Refresh to see the data."
            : "Live updates paused — reload the page to resume."}
        </p>
      )}
    </div>
  );
}
