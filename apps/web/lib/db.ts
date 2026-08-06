/**
 * Direct Postgres access for React Server Components.
 *
 * RSC reads the database directly rather than round-tripping through FastAPI —
 * it halves latency on the dashboard (docs/06-api-auth.md §15). Mutations,
 * jobs, and streaming all still go through the API.
 *
 * Every tenant query MUST use tenantQuery(), which sets the session variables
 * the RLS policies read. See docs/08-infrastructure.md §28.
 */
import { Pool } from "pg";

declare global {
  // eslint-disable-next-line no-var
  var __seoosPool: Pool | undefined;
}

function getPool(): Pool {
  if (!global.__seoosPool) {
    global.__seoosPool = new Pool({
      connectionString: process.env.DATABASE_URL,
      max: 6,
      idleTimeoutMillis: 30_000,
    });
  }
  return global.__seoosPool;
}

/** A query with NO tenant scope. Auth lookups and non-tenant tables only. */
export async function systemQuery<T = Record<string, unknown>>(
  sql: string,
  params: unknown[] = [],
): Promise<T[]> {
  const { rows } = await getPool().query(sql, params);
  return rows as T[];
}

/**
 * A query scoped to one tenant, inside a transaction.
 *
 * set_config(..., true) is transaction-scoped, so a pooled connection can never
 * leak one request's tenant into the next.
 */
export async function tenantQuery<T = Record<string, unknown>>(
  orgId: string,
  role: string,
  sql: string,
  params: unknown[] = [],
  clientId?: string,
): Promise<T[]> {
  const client = await getPool().connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.current_org_id', $1, true)", [orgId]);
    await client.query("SELECT set_config('app.current_role', $1, true)", [role]);
    if (clientId) {
      await client.query("SELECT set_config('app.current_client_id', $1, true)", [clientId]);
    }
    const { rows } = await client.query(sql, params);
    await client.query("COMMIT");
    return rows as T[];
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
