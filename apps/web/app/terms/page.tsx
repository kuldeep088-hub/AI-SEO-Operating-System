import type { Metadata } from "next";
import Link from "next/link";

import { LegalPage, Section } from "@/components/public-chrome";
import { COMPANY } from "@/lib/company";

export const metadata: Metadata = {
  title: `Terms of service — ${COMPANY.appName}`,
  description: "The agreement covering use of the app.",
};

/**
 * NOT LEGAL ADVICE. A plain, honest starting draft — have a lawyer read it
 * before relying on it, and fill in the placeholders in lib/company.ts.
 */
export default function Terms() {
  return (
    <LegalPage title="Terms of service">
      <Section heading="The agreement">
        <p>
          These terms cover your use of {COMPANY.appName}, operated by{" "}
          {COMPANY.operator}. Using the app means you accept them. If you are
          agreeing on behalf of a company, you confirm you are allowed to.
        </p>
      </Section>

      <Section heading="What you need">
        <p>
          A Google account, and permission to view the Search Console and
          Analytics properties you connect. You are responsible for having that
          permission — connecting a property you are not authorised to access is
          a breach of these terms and quite possibly of your agreement with
          whoever owns it.
        </p>
      </Section>

      <Section heading="Your account">
        <p>
          Keep your Google account secure; anyone who controls it controls your
          data here. Tell us promptly at{" "}
          <a href={`mailto:${COMPANY.contactEmail}`}>{COMPANY.contactEmail}</a>{" "}
          if you think your account has been compromised.
        </p>
      </Section>

      <Section heading="What you may not do">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Connect properties you do not have authorisation to access.
          </li>
          <li>
            Attempt to reach another customer&rsquo;s data, or probe the service
            for weaknesses without written permission. If you find a security
            problem, report it to{" "}
            <a href={`mailto:${COMPANY.contactEmail}`}>
              {COMPANY.contactEmail}
            </a>{" "}
            — we would much rather hear from you than not.
          </li>
          <li>
            Resell or redistribute the service as your own without a written
            agreement.
          </li>
          <li>
            Use the app to break the law, or Google&rsquo;s terms.
          </li>
        </ul>
      </Section>

      <Section heading="Your data stays yours">
        <p>
          You keep all rights to the data you connect and anything the app
          derives from it. We claim no ownership. Our handling of it is described
          in the{" "}
          <Link href="/privacy" className="text-body underline underline-offset-2 hover:text-title">
            privacy policy
          </Link>
          , which forms part of these terms.
        </p>
      </Section>

      <Section heading="Availability, honestly stated">
        <p>
          The app is provided as-is, without warranty. We do not promise an
          uptime figure and there is no support commitment beyond a good-faith
          effort to answer email. The app depends on Google&rsquo;s APIs; when
          Google changes them, imposes quota, or has an outage, parts of the app
          will stop working until we adapt.
        </p>
        <p>
          Reports and analyses are informational. They describe what the data
          shows and note when things happened together; they do not establish
          that one thing caused another, and they are not a substitute for your
          own professional judgement.
        </p>
      </Section>

      <Section heading="Liability">
        <p>
          To the fullest extent the law allows, {COMPANY.operator} is not liable
          for indirect, incidental or consequential loss, or for lost profits,
          revenue or data. Where liability cannot be excluded, it is limited to
          the amount you paid for the service in the twelve months before the
          claim.
        </p>
      </Section>

      <Section heading="Ending it">
        <p>
          You can stop using the app whenever you like and ask for deletion under
          the privacy policy. We may suspend or close an account that breaches
          these terms, and will say why unless we are legally barred from doing
          so.
        </p>
      </Section>

      <Section heading="Changes and governing law">
        <p>
          We will give notice of material changes to these terms by email before
          they take effect. These terms are governed by the laws of{" "}
          {COMPANY.jurisdiction}.
        </p>
      </Section>
    </LegalPage>
  );
}
