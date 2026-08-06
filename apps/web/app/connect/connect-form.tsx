"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type GscProp = {
  site_url: string;
  display: string;
  permission: string;
  usable: boolean;
};
type Ga4Prop = {
  property_id: string;
  display: string;
  account: string;
};

export function ConnectForm({ apiUrl }: { apiUrl: string }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [gsc, setGsc] = useState<GscProp[]>([]);
  const [ga4, setGa4] = useState<Ga4Prop[]>([]);

  const [gscChoice, setGscChoice] = useState("");
  const [ga4Choice, setGa4Choice] = useState("");
  const [clientName, setClientName] = useState("");
  const [domain, setDomain] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${apiUrl}/v1/google/properties`, { credentials: "include" })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
        return r.json();
      })
      .then((body) => {
        setGsc(body.data.search_console);
        setGa4(body.data.analytics);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [apiUrl]);

  // Choosing a Search Console property fills in the client name and domain,
  // because the property id already contains them.
  function chooseGsc(value: string) {
    setGscChoice(value);
    const prop = gsc.find((p) => p.site_url === value);
    if (!prop) return;
    const host = prop.display.replace(/^https?:\/\//, "").replace(/\/$/, "");
    setDomain(host);
    if (!clientName) {
      const base = host.split(".")[0];
      setClientName(base.charAt(0).toUpperCase() + base.slice(1));
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(`${apiUrl}/v1/google/connect`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_name: clientName,
          domain,
          gsc_property: gscChoice || null,
          ga4_property_id: ga4Choice || null,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail ?? `HTTP ${res.status}`);
      setDone(body.data.site_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <p className="body-sm mt-10 text-muted">Loading your Google properties…</p>
    );
  }

  if (done) {
    return (
      <section className="mt-10 rounded-lg border border-line bg-surface p-6">
        <h2 className="body-emphasis text-title">Connected.</h2>
        <p className="body-base mt-2 text-subtle">
          Backfilling up to 16 months of history now. It runs in the background —
          the dashboard fills in as data lands.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex h-10 items-center rounded-md bg-accent px-4 text-on-accent transition-opacity hover:opacity-90"
        >
          <span className="body-sm">Open dashboard</span>
        </Link>
      </section>
    );
  }

  const usable = gsc.filter((p) => p.usable);

  return (
    <form onSubmit={submit} className="mt-10 space-y-6">
      {error && (
        <div className="rounded-md border border-negative/30 bg-negative/10 px-4 py-3">
          <p className="body-sm text-negative">{error}</p>
        </div>
      )}

      <Field
        label="Search Console property"
        hint={
          usable.length
            ? `${usable.length} available`
            : "None found — check the property is shared with this Google account"
        }
      >
        <select
          value={gscChoice}
          onChange={(e) => chooseGsc(e.target.value)}
          className="body-sm h-10 w-full rounded-md border border-line bg-surface px-3 text-title"
        >
          <option value="">Not connected</option>
          {usable.map((p) => (
            <option key={p.site_url} value={p.site_url}>
              {p.display} ({p.permission})
            </option>
          ))}
        </select>
      </Field>

      <Field label="Analytics property" hint={`${ga4.length} available`}>
        <select
          value={ga4Choice}
          onChange={(e) => setGa4Choice(e.target.value)}
          className="body-sm h-10 w-full rounded-md border border-line bg-surface px-3 text-title"
        >
          <option value="">Not connected</option>
          {ga4.map((p) => (
            <option key={p.property_id} value={p.property_id}>
              {p.display} — {p.account}
            </option>
          ))}
        </select>
      </Field>

      <div className="grid gap-6 sm:grid-cols-2">
        <Field label="Client name">
          <input
            required
            value={clientName}
            onChange={(e) => setClientName(e.target.value)}
            placeholder="Acme Corporation"
            className="body-sm h-10 w-full rounded-md border border-line bg-surface px-3 text-title"
          />
        </Field>
        <Field label="Domain">
          <input
            required
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="acme.com"
            className="body-sm h-10 w-full rounded-md border border-line bg-surface px-3 text-title"
          />
        </Field>
      </div>

      <button
        type="submit"
        disabled={submitting || (!gscChoice && !ga4Choice)}
        className="inline-flex h-10 items-center rounded-md bg-accent px-4 text-on-accent transition-opacity hover:opacity-90 disabled:opacity-40"
      >
        <span className="body-sm">
          {submitting ? "Connecting…" : "Connect and backfill"}
        </span>
      </button>

      <p className="caption text-muted">
        The backfill pulls up to 16 months — Search Console&apos;s full retention.
        It runs in the background and can take a few minutes on a large site.
      </p>
    </form>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mono-label mb-2 block uppercase text-muted">
        {label}
        {hint && <span className="ml-2 normal-case text-muted">· {hint}</span>}
      </span>
      {children}
    </label>
  );
}
