import type { Metadata } from "next";

import { LegalPage, Section } from "@/components/public-chrome";
import { COMPANY, SCOPES } from "@/lib/company";

export const metadata: Metadata = {
  title: `Privacy policy — ${COMPANY.appName}`,
  description:
    "What Google data this app reads, why, where it is stored, and how to delete it.",
};

/**
 * Google's OAuth reviewers read this page against the scopes in the submission.
 * Three things they specifically look for, all present below:
 *
 *   1. The Limited Use disclosure, verbatim, with a link to the policy.
 *   2. Each requested scope named, with what it is used for.
 *   3. A working route to revoke access and delete data.
 *
 * NOT LEGAL ADVICE. This is a solid, accurate starting draft written against
 * what the code actually does — have a lawyer read it before you rely on it,
 * and fill in the placeholders in lib/company.ts first.
 */
export default function Privacy() {
  return (
    <LegalPage title="Privacy policy">
      <Section heading="Who this is">
        <p>
          {COMPANY.appName} (&ldquo;the app&rdquo;) is operated by{" "}
          {COMPANY.legalName}, {COMPANY.postalAddress}. Questions about this
          policy or about your data go to{" "}
          <a href={`mailto:${COMPANY.contactEmail}`}>{COMPANY.contactEmail}</a>,
          and we answer them.
        </p>
      </Section>

      <Section heading="What the app reads from your Google account">
        <p>
          The app asks for the narrowest access that lets it work. Every scope is
          read-only: it cannot publish, change or delete anything in your Search
          Console or Analytics properties.
        </p>
        <ul className="space-y-4">
          {SCOPES.map((s) => (
            <li key={s.scope}>
              <span className="body-sm-strong text-ink">{s.label}</span>
              <span className="caption-mono ml-2 text-mute">{s.scope}</span>
              <p className="mt-1">{s.why}</p>
            </li>
          ))}
        </ul>
        <p>
          You choose which Search Console and Analytics properties to connect.
          The app reads only the ones you pick, and Google lets you decline any
          individual permission on the consent screen — the app will tell you
          what it cannot do rather than fail silently.
        </p>
      </Section>

      <Section heading="Limited Use disclosure">
        <p>
          {COMPANY.appName}&rsquo;s use and transfer of information received from
          Google APIs to any other app will adhere to the{" "}
          <a
            href="https://developers.google.com/terms/api-services-user-data-policy"
            target="_blank"
            rel="noopener noreferrer"
          >
            Google API Services User Data Policy
          </a>
          , including the Limited Use requirements.
        </p>
        <p>
          Concretely, and without qualification: your Google data is not sold, is
          not transferred to third parties except as needed to provide the
          service you asked for, is not used for advertising, and is not read by
          a human except where you have explicitly asked us to help you with a
          support request, or where the law requires it.
        </p>
        <p>
          The app does not use your Google data to train machine-learning models,
          general-purpose or otherwise.
        </p>
      </Section>

      <Section heading="What else we store">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Your name, email address and profile picture, from Google sign-in.
          </li>
          <li>
            The Search Console and Analytics metrics for the properties you
            connect — clicks, impressions, positions, queries, pages, sessions
            and conversions — kept so the app can show change over time.
          </li>
          <li>
            The names and domains of the clients and sites you set up.
          </li>
          <li>
            An audit record of significant account actions, with the IP address
            and browser user-agent they came from, kept for security
            investigation.
          </li>
        </ul>
      </Section>

      <Section heading="Where it is stored, and who can reach it">
        <p>
          Data is stored in a PostgreSQL database on a server controlled by{" "}
          {COMPANY.legalName}. Your Google access and refresh tokens are
          encrypted at rest with a key held outside the database, so a copy of
          the database alone does not grant access to your Google account.
        </p>
        <p>
          Every organisation&rsquo;s rows are separated inside the database by
          row-level security, enforced by PostgreSQL itself rather than by
          application code, so one customer cannot read another&rsquo;s data even
          if a query is written incorrectly.
        </p>
        <p>
          Traffic between your browser and the app is encrypted with TLS.
        </p>
      </Section>

      <Section heading="Who we share it with">
        <p>
          Nobody. There are no advertising networks, no analytics trackers on
          this app, and no data brokers. The only outbound connections the app
          makes with your data are back to Google&rsquo;s own APIs, using the
          access you granted.
        </p>
        <p>
          We would disclose data if compelled by valid legal process, and would
          tell you unless prohibited from doing so.
        </p>
      </Section>

      <Section heading="Revoking access and deleting your data">
        <p>
          You can disconnect Google at any time from the app&rsquo;s settings, or
          from{" "}
          <a
            href="https://myaccount.google.com/permissions"
            target="_blank"
            rel="noopener noreferrer"
          >
            your Google account permissions page
          </a>
          . Revoking there immediately stops all further access; the stored
          tokens become useless and are deleted on the next sync attempt.
        </p>
        <p>
          To delete your account and everything associated with it, email{" "}
          <a href={`mailto:${COMPANY.contactEmail}`}>{COMPANY.contactEmail}</a>{" "}
          from the address you signed up with. Deletion is permanent, covers the
          Search Console and Analytics data we cached, and is completed within 30
          days. Backups are rotated on a 14-day cycle, so a copy may persist in
          an encrypted backup for up to that long after deletion.
        </p>
      </Section>

      <Section heading="How long we keep things">
        <ul className="list-disc space-y-2 pl-5">
          <li>Search Console and Analytics data: while your account is open.</li>
          <li>
            Sign-in sessions: 30 days, then they expire and are collected
            automatically.
          </li>
          <li>Audit records: 12 months.</li>
          <li>Encrypted backups: 14 days.</li>
        </ul>
      </Section>

      <Section heading="Your rights">
        <p>
          Depending on where you live you may have rights to access, correct,
          export or erase your personal data, and to object to processing. Email{" "}
          <a href={`mailto:${COMPANY.contactEmail}`}>{COMPANY.contactEmail}</a>{" "}
          and we will action it within 30 days. We do not charge for this and we
          will not make you justify the request.
        </p>
      </Section>

      <Section heading="Children">
        <p>
          The app is a professional tool and is not directed at anyone under 16.
          We do not knowingly collect their data.
        </p>
      </Section>

      <Section heading="Changes">
        <p>
          If this policy changes materially — particularly if the app ever asks
          for a new Google scope — we will email registered users before the
          change takes effect, rather than quietly editing this page. The date at
          the top always reflects the last substantive revision.
        </p>
      </Section>
    </LegalPage>
  );
}
