/**
 * Details that appear on the public pages Google's OAuth reviewers read.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 *  FILL THESE IN BEFORE SUBMITTING FOR VERIFICATION.
 *
 *  Google checks that the homepage and privacy policy are on the same domain
 *  you verified in Search Console, and that the privacy policy names a real
 *  contact. Placeholder text left here is a rejection.
 * ─────────────────────────────────────────────────────────────────────────────
 */

export const COMPANY = {
  /** The product name. Must match the "App name" on the OAuth consent screen. */
  appName: "AI SEO Operating System",

  /** The operator. Must match the legal entity you verify the domain as. */
  legalName: "Growleads Agency",

  /** Where the app is served. Must be the domain verified in Search Console. */
  domain: "seo.growleadsagency.com",

  /** Reachable address for privacy questions and data-deletion requests. */
  contactEmail: "anuj@growleadsagency.com",

  /** Postal address — Google's reviewers expect one on the privacy policy. */
  postalAddress: "TODO — registered business address",

  /** Governing law for the terms of service. */
  jurisdiction: "India",

  /** Last substantive revision, shown on both legal pages. */
  lastUpdated: "6 August 2026",
} as const;

/**
 * The scopes the app requests, and the plain-English reason for each.
 *
 * Google requires a per-scope justification in the verification submission, and
 * the reviewer cross-checks it against what the app visibly does. Keeping the
 * list here means the consent screen copy, the privacy policy and the homepage
 * cannot drift apart from each other.
 */
export const SCOPES = [
  {
    scope: "openid, userinfo.email, userinfo.profile",
    label: "Your name and email address",
    why: "To create your account and sign you in. Nothing else uses it.",
    sensitive: false,
  },
  {
    scope: "webmasters.readonly",
    label: "Search Console — read only",
    why: "To read clicks, impressions, average position and the queries your pages rank for. This is the data every report and chart is built from.",
    sensitive: true,
  },
  {
    scope: "analytics.readonly",
    label: "Google Analytics — read only",
    why: "To read sessions, engagement and conversions per landing page, so search performance can be tied to what visitors actually did.",
    sensitive: true,
  },
] as const;
