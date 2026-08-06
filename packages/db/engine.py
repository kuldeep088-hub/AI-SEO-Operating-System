"""Postgres connection pool, and the transaction wrapper that enforces tenancy.

The `tenant_tx` helper is the single most important function in the codebase.
Every query touching tenant data must run inside it, because it sets the
session variables the RLS policies read.

`set_config(..., true)` scopes the setting to the TRANSACTION. With a connection
pool this is the difference between correct isolation and a request inheriting
the previous request's tenant — the most dangerous bug this architecture can
have. See docs/08-infrastructure.md §28.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from packages.core.config import settings
from packages.core.logging import get_logger

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(
    min_size: int = 2, max_size: int = 10, dsn: str | None = None
) -> asyncpg.Pool:
    """Create the shared pool.

    `dsn` defaults to the least-privilege application role, which is what the
    API and web app want — RLS applies, so a query that forgets tenant_tx()
    returns nothing rather than everything. The worker overrides it; see
    settings.worker_database_url for why.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn or settings.database_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60,
            server_settings={"application_name": "seo-os"},
        )
        log.info("db.pool_created", min_size=min_size, max_size=max_size)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("db.pool_closed")


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialised — call init_pool() during startup")
    return _pool


@asynccontextmanager
async def tenant_tx(
    org_id: str,
    role: str = "admin",
    client_id: str | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """A transaction scoped to one tenant. RLS policies read these settings.

    Never query tenant tables outside this context manager.
    """
    async with pool().acquire() as conn, conn.transaction():
        await conn.execute("SELECT set_config('app.current_org_id', $1, true)", org_id)
        await conn.execute("SELECT set_config('app.current_role', $1, true)", role)
        if client_id:
            await conn.execute(
                "SELECT set_config('app.current_client_id', $1, true)", client_id
            )
        yield conn


@asynccontextmanager
async def system_tx() -> AsyncIterator[asyncpg.Connection]:
    """A transaction with NO tenant scope.

    Only for auth (looking up a session before the org is known) and for
    maintenance jobs that touch non-tenant tables. Everything else uses
    tenant_tx.
    """
    async with pool().acquire() as conn, conn.transaction():
        yield conn


async def healthcheck() -> dict[str, Any]:
    try:
        async with pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
            version = await conn.fetchval("SHOW server_version")
            has_vector = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
            )
        return {"ok": True, "version": version, "pgvector": has_vector}
    except Exception as exc:  # noqa: BLE001 — health checks report, never raise
        return {"ok": False, "error": str(exc)}
