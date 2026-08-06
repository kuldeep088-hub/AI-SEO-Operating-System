/**
 * One-click demo sign-in.
 *
 * Exchanges a token in the query string for the session cookie, so the demo is
 * a link rather than a DevTools exercise.
 *
 * Deliberately narrow, because signing in from a URL is otherwise a bad idea:
 *   · dev environment only
 *   · the session must already exist in the database
 *   · and it must belong to the demo organisation, never a real one
 *
 * Real sign-in is Google OAuth (docs/06-api-auth.md §16). This route cannot
 * authenticate a real user even if the token is guessed.
 */
import { createHash } from "node:crypto";
import { NextResponse } from "next/server";

import { systemQuery } from "@/lib/db";
import { SESSION_COOKIE } from "@/lib/session";

export const dynamic = "force-dynamic";

const DEMO_SLUG = "growleads-demo";

export async function GET(request: Request) {
  const origin = new URL(request.url).origin;

  if (process.env.NODE_ENV === "production" && process.env.ENV !== "dev") {
    return NextResponse.json({ error: "Demo sign-in is disabled." }, { status: 404 });
  }

  const token = new URL(request.url).searchParams.get("t");
  if (!token) {
    return NextResponse.redirect(`${origin}/login`);
  }

  const rows = await systemQuery<{ slug: string }>(
    `SELECT o.slug
     FROM   sessions s
     JOIN   organizations o ON o.id = s.org_id
     WHERE  s.token_hash = $1
       AND  s.revoked_at IS NULL
       AND  s.expires_at > now()
     LIMIT  1`,
    [createHash("sha256").update(token).digest("hex")],
  );

  if (rows[0]?.slug !== DEMO_SLUG) {
    return NextResponse.redirect(`${origin}/login?error=demo_expired`);
  }

  const response = NextResponse.redirect(origin + "/");
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 3600,
  });
  return response;
}
