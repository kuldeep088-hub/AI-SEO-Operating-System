from __future__ import annotations

import os
from collections.abc import AsyncIterator
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio

# DATABASE_URL is now the least-privilege application role (seoos_app), so it
# cannot create the fixtures. ADMIN_DATABASE_URL is the owner. Falling back to
# DATABASE_URL keeps a single-role setup (CI, throwaway databases) working.
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://seoos:seoos_local_dev@127.0.0.1:5432/seoos"
)
ADMIN_DATABASE_URL = os.environ.get("ADMIN_DATABASE_URL") or DATABASE_URL


def _as_user(url: str, user: str) -> str:
    """Rewrite the URL's user, handling both TCP and unix-socket forms.

    Docker gives postgresql://seoos:pw@host:5432/seoos
    pgserver gives postgresql://postgres:@/seoos?host=/path/to/socket
    """
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{user}@{host}{port}" if host else f"{user}@"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    """Privileged connection for fixture setup. Owns the tables, bypasses RLS."""
    c = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        yield c
    finally:
        await c.close()


@pytest_asyncio.fixture
async def app_conn() -> AsyncIterator[asyncpg.Connection]:
    """Connection as the application role — the one RLS actually applies to.

    This distinction is the whole point: the owner bypasses RLS unless FORCE is
    set, so testing isolation as the owner would prove nothing.
    """
    c = await asyncpg.connect(_as_user(ADMIN_DATABASE_URL, "seoos_app"))
    try:
        yield c
    finally:
        await c.close()


@pytest_asyncio.fixture
async def two_orgs(conn: asyncpg.Connection) -> AsyncIterator[dict[str, str]]:
    """Two organizations, each with a client and a site.

    The whole isolation suite rests on this: org A must never see org B.
    """
    ids: dict[str, str] = {}
    for key in ("a", "b"):
        org = await conn.fetchval(
            "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id",
            f"Test Org {key.upper()}",
            f"test-org-{key}-{os.urandom(4).hex()}",
        )
        client = await conn.fetchval(
            "INSERT INTO clients (org_id, name) VALUES ($1, $2) RETURNING id",
            org, f"Client {key.upper()}",
        )
        site = await conn.fetchval(
            """INSERT INTO sites (org_id, client_id, domain, start_url)
               VALUES ($1, $2, $3, $4) RETURNING id""",
            org, client, f"{key}-{os.urandom(3).hex()}.example.com",
            f"https://{key}.example.com/",
        )
        await conn.execute(
            """INSERT INTO issues (org_id, site_id, rule_key, severity, affected_count)
               VALUES ($1, $2, 'http.404', 'critical', 3)""",
            org, site,
        )
        ids[f"org_{key}"] = str(org)
        ids[f"client_{key}"] = str(client)
        ids[f"site_{key}"] = str(site)

    yield ids

    for key in ("a", "b"):
        await conn.execute("DELETE FROM organizations WHERE id = $1", ids[f"org_{key}"])
