/**
 * Google OAuth error codes, translated for the person who hit them.
 *
 * Google reports a failed authorisation by redirecting back to our callback
 * with `?error=<code>` and no `code` parameter. That is the normal shape of
 * "the user pressed Cancel", and on a public deployment it will be one of the
 * most common things that happens — people open the consent screen, read the
 * list of permissions, and think better of it.
 *
 * These strings live here rather than in `packages/` because the API never
 * needs them: it logs the raw code and forwards it in the redirect, and this
 * is the only place a human reads one. A Python copy would be dead code and a
 * second thing to keep in sync.
 *
 * Two codes are worth recognising, because they look like application faults
 * and are not:
 *
 *  - `access_denied` is also what Google sends when the OAuth app is still in
 *    Testing and the account is not on the Test users list.
 *  - `admin_policy_enforced` means the user's Workspace admin blocks the app.
 *    Nothing the user or we can do; it needs their IT administrator.
 *
 * See docs/06-api-auth.md §16.
 */

const MESSAGES: Record<string, string> = {
  access_denied:
    "You cancelled the Google sign-in, or the account you chose does not have access to this app yet. Nothing was connected and nothing was shared. You can try again, with a different Google account if you have one.",
  admin_policy_enforced:
    "Your Google Workspace administrator blocks this app, or blocks third-party apps that request Search Console and Analytics access. Ask your IT administrator to allow it, or sign in with a personal Google account that owns the properties.",
  disallowed_useragent:
    "Google refused the sign-in because of the browser this page opened in. Open the app directly in Safari, Chrome or Firefox rather than inside another app's built-in browser, then try again.",
  org_internal:
    "This app is restricted to a single Google Workspace organisation, and the account you chose is outside it.",
  redirect_uri_mismatch:
    "This app's Google configuration is incomplete — the address Google was asked to return to is not one it recognises. That is a setup problem on our side, not something you did wrong.",
  invalid_scope:
    "This app asked Google for a permission it is not allowed to request. That is a configuration problem on our side.",
  invalid_client:
    "This app's Google credentials are not valid. That is a configuration problem on our side, not something you did wrong.",
  server_error:
    "Google had an internal error while signing you in. Nothing is wrong with your account — try again in a moment.",
  temporarily_unavailable:
    "Google is temporarily unable to complete sign-ins. Try again in a few minutes.",
  missing_code:
    "Google sent us back without an authorisation code, which usually means the sign-in was cancelled or timed out. Nothing was connected and nothing was shared.",
};

const FALLBACK =
  "Google could not complete the sign-in. Nothing was connected and nothing was shared. Try again, and if it keeps happening, get in touch.";

/**
 * Unknown codes fall back to a message that is still honest about what did and
 * did not happen — Google adds codes without warning, and a blank panel is
 * worse than a general explanation.
 */
export function describeOAuthError(code: string | undefined): string {
  if (!code) return FALLBACK;
  return MESSAGES[code] ?? FALLBACK;
}
