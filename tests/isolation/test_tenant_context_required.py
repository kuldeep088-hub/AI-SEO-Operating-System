"""Tenant tables must be reached with an org context set.

The isolation suite proved the RLS *policies* were correct. It never checked
that application code actually enters `tenant_tx()` before touching a protected
table, and that gap let the entire Google connect flow ship broken:

  * `store_connection()` INSERTed into `oauth_connections` on `system_tx`,
    where `app.current_org_id` is unset. The policy is
    `org_id = nullif(current_setting('app.current_org_id', true), '')::uuid`,
    which evaluates to NULL, so the WITH CHECK failed with
    InsufficientPrivilegeError — a 500 the moment anyone connected Google.
  * Every *read* of the same table on `system_tx` matched zero rows instead of
    erroring, which is worse: `/v1/auth/me` reported `data_scopes_granted:
    false` forever, and `/connect` kept asking an org to grant access it had
    already granted.

The asymmetry is the lesson. A write without tenant context fails loudly; a
read without it fails silently.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from packages.db.engine import close_pool, init_pool, system_tx, tenant_tx


@pytest_asyncio.fixture(autouse=True)
async def engine_pool() -> AsyncIterator[None]:
    """These tests exercise the real engine, not a hand-rolled connection.

    The rest of the isolation suite connects with bare asyncpg, which is what
    let this class of bug through: it tested the policies, never the code path
    the application actually takes. `init_pool()` defaults to the app role, so
    RLS genuinely applies here.
    """
    await init_pool(min_size=1, max_size=2)
    try:
        yield
    finally:
        await close_pool()


@pytest.mark.asyncio
async def test_writing_a_tenant_table_without_context_is_refused(
    two_orgs: dict[str, str],
) -> None:
    """The failure mode that produced the 500 on /v1/google/callback.

    A direct VALUES insert, not INSERT … SELECT: a SELECT that returns no rows
    inserts nothing and therefore never trips WITH CHECK, so it would pass this
    test while proving nothing.
    """
    with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
        async with system_tx() as conn:
            await conn.execute(
                "INSERT INTO clients (org_id, name) VALUES ($1, 'No Context')",
                two_orgs["org_a"],
            )


@pytest.mark.asyncio
async def test_reading_a_tenant_table_without_context_returns_nothing(
    two_orgs: dict[str, str], conn: asyncpg.Connection
) -> None:
    """The silent half — no error, just an empty result that reads as 'absent'."""
    await conn.execute(
        "INSERT INTO clients (org_id, name) VALUES ($1, 'Context Probe')",
        two_orgs["org_a"],
    )

    async with system_tx() as sys_conn:
        without_context = await sys_conn.fetchval(
            "SELECT count(*) FROM clients WHERE org_id = $1", two_orgs["org_a"]
        )

    async with tenant_tx(two_orgs["org_a"], "owner") as tenant_conn:
        with_context = await tenant_conn.fetchval(
            "SELECT count(*) FROM clients WHERE org_id = $1", two_orgs["org_a"]
        )

    assert without_context == 0, (
        "no error is raised — this is why a missing tenant_tx on a read is "
        "harder to spot than on a write"
    )
    assert with_context > 0

    await conn.execute(
        "DELETE FROM clients WHERE org_id = $1 AND name = 'Context Probe'",
        two_orgs["org_a"],
    )


@pytest.mark.asyncio
async def test_writing_with_context_succeeds(two_orgs: dict[str, str]) -> None:
    """The corrected path: same statement, inside tenant_tx."""
    async with tenant_tx(two_orgs["org_a"], "owner") as conn:
        await conn.execute(
            "INSERT INTO clients (org_id, name) VALUES ($1, 'Context OK')",
            two_orgs["org_a"],
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM clients WHERE name = 'Context OK'"
        ) == 1
