"""Tenant isolation — the highest-value tests in this codebase.

A bug that leaks one client's data to another is an incident with the agency's
own customers (docs/09-security-ops.md §29). These tests assert that Postgres
RLS holds even when the application layer is wrong or absent — every query below
is deliberately unfiltered.
"""

from __future__ import annotations

import asyncpg
import pytest

# Every table carrying org_id. A new tenant table must be added here.
TENANT_TABLES = [
    "clients", "sites", "portal_tokens", "oauth_connections", "sync_state",
    "lighthouse_runs", "rank_history", "crawls", "pages", "internal_links",
    "issues", "keyword_clusters", "competitors", "backlinks",
    "briefs", "drafts", "publications", "agent_runs", "embeddings",
    "memories", "jobs", "schedules", "notifications", "reports", "api_keys",
]


async def _scope(conn: asyncpg.Connection, org_id: str, role: str = "admin") -> None:
    await conn.execute("SELECT set_config('app.current_org_id', $1, true)", org_id)
    await conn.execute("SELECT set_config('app.current_role', $1, true)", role)


@pytest.mark.parametrize("table", TENANT_TABLES)
async def test_unfiltered_select_cannot_cross_tenants(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str], table: str
) -> None:
    """A SELECT with no WHERE clause must still return only one tenant's rows."""
    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"])
        rows = await app_conn.fetch(f"SELECT org_id FROM {table}")  # noqa: S608
    assert all(str(r["org_id"]) == two_orgs["org_a"] for r in rows), (
        f"{table} leaked rows across tenants"
    )


async def test_cannot_read_other_orgs_site_by_id(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """Knowing another tenant's UUID must not be enough to read it."""
    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"])
        row = await app_conn.fetchrow(
            "SELECT * FROM sites WHERE id = $1", two_orgs["site_b"]
        )
    assert row is None


async def test_cannot_insert_into_another_org(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """WITH CHECK must block writing a row tagged with another tenant's org_id."""
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with app_conn.transaction():
            await _scope(app_conn, two_orgs["org_a"])
            await app_conn.execute(
                """INSERT INTO clients (org_id, name) VALUES ($1, 'Injected')""",
                two_orgs["org_b"],
            )


async def test_cannot_update_another_orgs_row(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"])
        result = await app_conn.execute(
            "UPDATE sites SET domain = 'hijacked.com' WHERE id = $1", two_orgs["site_b"]
        )
    assert result == "UPDATE 0"


async def test_cannot_delete_another_orgs_row(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"])
        result = await app_conn.execute(
            "DELETE FROM issues WHERE org_id = $1", two_orgs["org_b"]
        )
    assert result == "DELETE 0"


async def test_no_org_context_returns_nothing(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """Forgetting to set the tenant must fail closed, not open."""
    async with app_conn.transaction():
        rows = await app_conn.fetch("SELECT * FROM sites")
    assert rows == []


async def test_client_viewer_confined_to_its_own_client(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str], conn: asyncpg.Connection
) -> None:
    """A portal viewer must not reach a sibling client in the same org.

    This is the boundary exposed to people outside the agency.
    """
    second_client = await conn.fetchval(
        "INSERT INTO clients (org_id, name) VALUES ($1, 'Sibling') RETURNING id",
        two_orgs["org_a"],
    )
    sibling_site = await conn.fetchval(
        """INSERT INTO sites (org_id, client_id, domain, start_url)
           VALUES ($1, $2, 'sibling.example.com', 'https://sibling.example.com/')
           RETURNING id""",
        two_orgs["org_a"], second_client,
    )

    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"], role="client_viewer")
        await app_conn.execute(
            "SELECT set_config('app.current_client_id', $1, true)", two_orgs["client_a"]
        )
        visible = await app_conn.fetch("SELECT id, client_id FROM sites")

    visible_ids = {str(r["id"]) for r in visible}
    assert two_orgs["site_a"] in visible_ids
    assert str(sibling_site) not in visible_ids, "client_viewer saw a sibling client"


async def test_transaction_scoped_settings_do_not_leak(
    app_conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """The pooling trap: one transaction's tenant must not survive into the next.

    set_config(..., true) is transaction-scoped. If this ever fails, a pooled
    connection is carrying tenant context between requests.
    """
    async with app_conn.transaction():
        await _scope(app_conn, two_orgs["org_a"])
        first = await app_conn.fetch("SELECT org_id FROM sites")
    assert first

    async with app_conn.transaction():
        leaked = await app_conn.fetch("SELECT org_id FROM sites")
    assert leaked == [], "tenant context leaked across transactions"
