import Link from "next/link";
import { redirect } from "next/navigation";

import { PublicFooter, PublicHeader } from "@/components/public-chrome";
import { describeOAuthError } from "@/lib/oauth-errors";
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
  searchParams: Promise<{ error?: string; oauth_error?: string }>;
}) {
  if (await getPrincipal()) redirect("/");

  const { error, oauth_error: oauthError } = await searchParams;
  const apiUrl = process.env.API_URL ?? "http://localhost:8000";
  const apiUp = await isApiUp(apiUrl);

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <PublicHeader />

      <main className="flex flex-1 items-center justify-center px-6 py-20">
        <div className="w-full max-w-[420px]">
          <h1 className="subheading text-title">Sign in.</h1>
          <p className="body-sm mt-4 text-subtle">
            Search Console and Analytics for every client site, in one place,
            refreshed nightly.
          </p>

          {/* Google refused the authorisation and sent the user back here.
              Most often they pressed Cancel; sometimes their Workspace admin
              blocks the app. Either way they need to know nothing was shared
              and what to try next. */}
          {oauthError && (
            <div className="mt-8 rounded-md border border-line bg-fill-subtle px-4 py-3">
              <p className="body-sm text-title">Google sign-in didn&apos;t finish.</p>
              <p className="body-sm mt-2 text-subtle">
                {describeOAuthError(oauthError)}
              </p>
            </div>
          )}

          {error === "demo_expired" && (
            <div className="mt-8 rounded-md border border-line bg-fill-subtle px-4 py-3">
              <p className="body-sm text-negative">
                That demo link has expired. Generate a new one with{" "}
                <code className="mono-label">scripts/seed_demo.py</code>.
              </p>
            </div>
          )}

          {!apiUp && (
            <div className="mt-8 rounded-md border border-line bg-fill-subtle px-4 py-3">
              <p className="body-sm text-negative">
                The API isn&apos;t running, so sign-in can&apos;t start. Stop this
                server and run <code className="mono-label">./run.sh</code> from
                the project root — it starts Postgres, the API, the worker and
                this page together.
              </p>
            </div>
          )}

          {/* The single acid-lime action on this view. */}
          {apiUp ? (
            <a
              href={`${apiUrl}/v1/auth/google/start`}
              className="mt-10 flex h-11 w-full items-center justify-center rounded-md bg-accent text-on-accent transition-opacity hover:opacity-90"
              style={{
                fontSize: 14,
                fontWeight: 510,
                letterSpacing: "-0.011em",
                boxShadow: "var(--shadow-cta)",
              }}
            >
              Continue with Google
            </a>
          ) : (
            <button
              disabled
              className="mt-10 flex h-11 w-full cursor-not-allowed items-center justify-center rounded-md border border-line bg-transparent text-muted"
              style={{ fontSize: 14, fontWeight: 510 }}
            >
              Continue with Google
            </button>
          )}

          <div className="mt-12 space-y-6 border-t border-line pt-8">
            <div>
              <p className="mono-label uppercase text-subtle">Scopes</p>
              <p className="body-sm mt-2 text-muted">
                Only email and profile, to sign you in. Search Console and
                Analytics access is requested separately, later, on a screen that
                explains each one.
              </p>
            </div>
            <div>
              <p className="mono-label uppercase text-subtle">Data</p>
              {/* This used to read "never leaves this machine", which was true
                  of a laptop install and false the moment the app is hosted for
                  other people. Claims on a sign-in screen are read by Google's
                  reviewers too, so it now says something true of both. */}
              <p className="body-sm mt-2 text-muted">
                Read-only access, never sold or shared. The only outbound calls
                carrying your data are to Google&apos;s own APIs, using access
                you grant — see the{" "}
                <Link
                  href="/privacy"
                  className="text-body underline underline-offset-2 hover:text-title"
                >
                  privacy policy
                </Link>
                .
              </p>
            </div>
          </div>
        </div>
      </main>

      <PublicFooter />
    </div>
  );
}
