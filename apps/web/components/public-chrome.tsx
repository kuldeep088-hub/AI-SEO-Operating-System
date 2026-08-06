/**
 * Header and footer for the pages a logged-out visitor can reach.
 *
 * These pages exist for two audiences at once: people deciding whether to sign
 * up, and the Google reviewer checking that the app has a real homepage and a
 * reachable privacy policy on the verified domain. The footer links are the
 * part the reviewer looks for, so they are on every public page, not just one.
 */
import Link from "next/link";

import { COMPANY } from "@/lib/company";

export function PublicHeader() {
  return (
    <header className="border-b border-hairline bg-canvas">
      <nav className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-sm bg-primary">
            <span className="caption-mono text-on-primary">S</span>
          </span>
          <span className="body-sm-strong text-ink">AI SEO OS</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link href="/privacy" className="body-sm text-body hover:text-ink">
            Privacy
          </Link>
          <Link
            href="/login"
            className="flex h-9 items-center rounded-full bg-primary px-5 text-on-primary transition-opacity hover:opacity-90"
          >
            <span className="body-sm-strong">Sign in</span>
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-hairline bg-canvas">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="body-sm text-mute">
            © {COMPANY.lastUpdated.slice(-4)} {COMPANY.legalName}
          </p>
          <div className="flex flex-wrap items-center gap-6">
            <Link href="/privacy" className="body-sm text-body hover:text-ink">
              Privacy policy
            </Link>
            <Link href="/terms" className="body-sm text-body hover:text-ink">
              Terms of service
            </Link>
            <a
              href={`mailto:${COMPANY.contactEmail}`}
              className="body-sm text-body hover:text-ink"
            >
              Contact
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

/** Shared shell for the two legal pages, which are pure prose. */
export function LegalPage({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-canvas-soft">
      <PublicHeader />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="caption-mono uppercase text-mute">Legal</p>
        <h1 className="display-lg mt-2 text-ink">{title}</h1>
        <p className="body-sm mt-3 text-mute">
          Last updated {COMPANY.lastUpdated}
        </p>
        <div className="mt-10 space-y-8">{children}</div>
      </main>
      <PublicFooter />
    </div>
  );
}

/** A titled prose section. Keeps heading rhythm identical across both pages. */
export function Section({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="display-sm text-ink">{heading}</h2>
      <div className="mt-3 space-y-3 [&_a]:text-link [&_a]:underline [&_li]:body-md [&_li]:text-body [&_p]:body-md [&_p]:text-body">
        {children}
      </div>
    </section>
  );
}
