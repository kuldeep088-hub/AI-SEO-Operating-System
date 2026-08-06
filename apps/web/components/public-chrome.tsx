/**
 * Header and footer for the pages a logged-out visitor can reach.
 *
 * These pages serve two audiences at once: people deciding whether to sign up,
 * and the Google reviewer checking that the app has a real homepage and a
 * reachable privacy policy on the verified domain. The footer links are the
 * part the reviewer looks for, so they are on every public page.
 *
 * Styling follows DESIGN.md: fixed top bar, left logo, right links, no sidebar,
 * 1200px max width, and the white pill sign-up button that the doc calls the
 * second-highest-contrast element after the acid-lime CTA.
 */
import Link from "next/link";

import { COMPANY } from "@/lib/company";

function LogoMark() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      {/* Geometric glyph in white, per DESIGN.md's "Logo Mark". */}
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <path
          d="M2 9.5 L9 2.5 L16 9.5 L9 16.5 Z"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-paper"
        />
      </svg>
      <span className="text-paper" style={{ fontSize: 16, fontWeight: 510 }}>
        {COMPANY.appShortName}
      </span>
    </Link>
  );
}

export function PublicHeader() {
  return (
    <header className="border-b border-graphite bg-void">
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6">
        <LogoMark />
        <div className="flex items-center gap-2">
          <Link
            href="/privacy"
            className="caption rounded-md px-3 py-2 text-mist transition-colors hover:text-paper"
          >
            Privacy
          </Link>
          <Link
            href="/terms"
            className="caption rounded-md px-3 py-2 text-mist transition-colors hover:text-paper"
          >
            Terms
          </Link>
          {/* Neutral white pill — the nav CTA. The acid-lime button is
              reserved for the single primary action on the page itself. */}
          <Link
            href="/login"
            className="ml-2 flex h-9 items-center rounded-full bg-paper px-4 text-void transition-opacity hover:opacity-90"
            style={{ fontSize: 13, fontWeight: 510 }}
          >
            Sign in
          </Link>
        </div>
      </nav>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="border-t border-graphite bg-void">
      <div className="mx-auto max-w-[1200px] px-6 py-10">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="caption text-ash">
            {COMPANY.appName} · {COMPANY.lastUpdated.slice(-4)}
          </p>
          <div className="flex flex-wrap items-center gap-6">
            <Link href="/privacy" className="caption text-fog hover:text-mist">
              Privacy policy
            </Link>
            <Link href="/terms" className="caption text-fog hover:text-mist">
              Terms of service
            </Link>
            <a
              href={`mailto:${COMPANY.contactEmail}`}
              className="caption text-fog hover:text-mist"
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
    <div className="min-h-screen bg-void">
      <PublicHeader />
      <main className="mx-auto max-w-3xl px-6 py-20">
        <p className="mono-label uppercase text-fog">Legal</p>
        <h1 className="subheading mt-3 text-paper">{title}</h1>
        <p className="caption mt-3 text-ash">
          Last updated {COMPANY.lastUpdated}
        </p>
        <div className="mt-14 space-y-10">{children}</div>
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
      <h2 className="heading text-paper">{heading}</h2>
      <div className="mt-4 space-y-3 [&_a]:text-mist [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-paper [&_li]:body-sm [&_li]:text-fog [&_p]:body-sm [&_p]:text-fog">
        {children}
      </div>
    </section>
  );
}
