"""The application's own connection must be one RLS applies to.

test_cross_tenant.py proves the *policies* are correct, but it proves it on a
connection it opens itself as `seoos_app`. That leaves a gap wide enough to
drive a data leak through: nothing checked what role the application actually
connects as.

It connected as `postgres`. `scripts/pg.py start()` returned
`srv.get_uri(...)` — the bundled server's superuser URI — and run.sh exported it
as DATABASE_URL for the API, the worker and the web app. RLS does not apply to
superusers under any circumstances, FORCE or not, so every policy in migration
0001 was inert at runtime. The dashboard query in apps/web/app/page.tsx has no
org_id filter of its own (by design — RLS is meant to be the filter), so a user
whose organisation owned no sites was served every other organisation's clients.
Verified on 2026-08-06, fixed the same day.

This is the exact failure mode CLAUDE.md warns about: code that looks right,
passes its tests, and quietly loses the property the design depends on.
"""

from __future__ import annotations

import asyncpg
import pytest

from tests.conftest import DATABASE_URL

pytestmark = pytest.mark.asyncio


async def test_configured_app_url_is_not_superuser() -> None:
    """DATABASE_URL must not be a superuser. RLS never applies to one."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        role = await conn.fetchval("SELECT current_user")
        is_super = await conn.fetchval(
            "SELECT usesuper FROM pg_user WHERE usename = current_user"
        )
        bypasses = await conn.fetchval(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    finally:
        await conn.close()

    assert not is_super, (
        f"DATABASE_URL connects as superuser {role!r}. Every RLS policy is "
        f"bypassed and tenants can read each other's rows. Use seoos_app."
    )
    assert not bypasses, f"DATABASE_URL role {role!r} has BYPASSRLS."


async def test_configured_app_url_actually_has_rls_enforced(
    conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """Scoped to org A, the app's real connection must not see org B's site.

    Deliberately opens DATABASE_URL verbatim rather than using the app_conn
    fixture — the fixture rewrites the role, which is what hid the bug. The
    point here is that the URL the application is configured with is safe.
    """
    app = await asyncpg.connect(DATABASE_URL)
    try:
        async with app.transaction():
            await app.execute(
                "SELECT set_config('app.current_org_id', $1, true)", two_orgs["org_a"]
            )
            await app.execute("SELECT set_config('app.current_role', 'owner', true)")
            visible = await app.fetch("SELECT id, org_id FROM sites")
    finally:
        await app.close()

    org_ids = {str(r["org_id"]) for r in visible}
    assert org_ids <= {two_orgs["org_a"]}, (
        f"Scoped to org A, the application's connection saw sites from {org_ids}. "
        f"RLS is not being enforced on DATABASE_URL."
    )
