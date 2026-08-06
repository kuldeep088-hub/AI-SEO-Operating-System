import Link from "next/link";
import { redirect } from "next/navigation";

import { getPrincipal } from "@/lib/session";

export const dynamic = "force-dynamic";

/**
 * "Continue with Google" is a plain <a> to the API, so if the API is down the browser
 * lands on ERR_CONNECTION_REFUSED — a dead end that names neither the cause nor the fix.
 * One cheap probe lets the page say what is actually wrong instead.
 */
async function isApiUp(apiUrl: string): Promise<boolean> {
  // INTERNAL_API_URL keeps this probe on the loopback when deployed behind a
  // reverse proxy: /health is not exposed publicly (it reports the Postgres
  // version and pgvector state), and probing through TLS on every render would
  // be a handshake for nothing. Falls back to the public URL locally.
  const probeUrl = process.env.INTERNAL_API_URL ?? apiUrl;
  try {
    const res = await fetch(`${probeUrl}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  if (await getPrincipal()) redirect("/");

  const { error } = await searchParams;
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const apiUp = await isApiUp(apiUrl);

  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-16">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-primary">
            <span className="caption-mono text-on-primary">S</span>
          </div>
          <span className="body-sm-strong text-ink">AI SEO OS</span>
        </div>

        <h1 className="display-lg text-ink">Sign in.</h1>
        <p className="body-md mt-3 text-body">
          Local-first SEO for agencies. Runs on this machine, costs nothing to
          operate.
        </p>

        {error === "demo_expired" && (
          <div className="mt-6 rounded-sm border border-error-soft bg-error-soft/40 px-4 py-3">
            <p className="body-sm text-error-deep">
              That demo link has expired. Generate a new one with{" "}
              <code className="caption-mono">scripts/seed_demo.py</code>.
            </p>
          </div>
        )}

        {!apiUp && (
          <div className="mt-6 rounded-sm border border-error-soft bg-error-soft/40 px-4 py-3">
            <p className="body-sm text-error-deep">
              The API isn&apos;t running, so sign-in can&apos;t start. Stop this
              server and run <code className="caption-mono">./run.sh</code> from
              the project root — it starts Postgres, the API, the worker and this
              page together.
            </p>
          </div>
        )}

        {/* Primary CTA — ink IS the conversion target (DESIGN.md).
            Nav-scale 6px radius, consistent with the rest of the app shell. */}
        {apiUp ? (
          <a
            href={`${apiUrl}/v1/auth/google/start`}
            className="elevate-1 mt-8 flex h-12 w-full items-center justify-center gap-2 rounded-sm bg-primary text-on-primary transition-opacity hover:opacity-90"
          >
            <span className="body-sm-strong">Continue with Google</span>
          </a>
        ) : (
          <button
            disabled
            className="mt-8 flex h-12 w-full cursor-not-allowed items-center justify-center gap-2 rounded-sm border border-hairline bg-transparent text-mute"
          >
            <span className="body-sm-strong">Continue with Google</span>
          </button>
        )}

        <div className="mt-10 space-y-4 border-t border-hairline pt-6">
          <div>
            <p className="caption-mono uppercase text-mute">Scopes</p>
            <p className="body-sm mt-2 text-body">
              Only email and profile, to sign you in. Search Console and
              Analytics access is requested separately, later, on a screen that
              explains each one.
            </p>
          </div>
          <div>
            <p className="caption-mono uppercase text-mute">Data</p>
            {/* This used to read "never leaves this machine", which was true of
                a laptop install and false the moment the app is hosted for
                other people. Claims on a sign-in screen are read by Google's
                reviewers too, so it now says something true of both. */}
            <p className="body-sm mt-2 text-body">
              Read-only access, never sold or shared. The only outbound calls
              carrying your data are to Google&apos;s own APIs, using access you
              grant — see the{" "}
              <Link href="/privacy" className="text-link underline">
                privacy policy
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
