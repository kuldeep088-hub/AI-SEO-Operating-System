/**
 * Session resolution for Server Components.
 *
 * The session cookie is set by FastAPI on localhost:8000. Cookies are scoped by
 * host, not by port, so localhost:3000 reads the same cookie.
 */
import { createHash } from "node:crypto";
import { cookies } from "next/headers";

import { systemQuery } from "./db";

export const SESSION_COOKIE = "seoos_session";

export type Principal = {
  userId: string;
  orgId: string;
  role: string;
  email: string;
  name: string | null;
  orgName: string;
  brandColor: string;
};

function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

export async function getPrincipal(): Promise<Principal | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  if (!token) return null;

  const rows = await systemQuery<{
    user_id: string;
    org_id: string;
    role: string;
    email: string;
    name: string | null;
    org_name: string;
    brand_color: string;
  }>(
    `SELECT s.user_id, s.org_id, m.role, u.email, u.name,
            o.name AS org_name, o.brand_color
     FROM   sessions s
     JOIN   users u         ON u.id = s.user_id
     JOIN   memberships m   ON m.user_id = s.user_id AND m.org_id = s.org_id
     JOIN   organizations o ON o.id = s.org_id
     WHERE  s.token_hash = $1
       AND  s.revoked_at IS NULL
       AND  s.expires_at > now()
     LIMIT 1`,
    [hashToken(token)],
  );

  const row = rows[0];
  if (!row) return null;

  return {
    userId: row.user_id,
    orgId: row.org_id,
    role: row.role,
    email: row.email,
    name: row.name,
    orgName: row.org_name,
    brandColor: row.brand_color,
  };
}
