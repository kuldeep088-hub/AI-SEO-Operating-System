"""The GSC⋈GA4 view must not become a hole in tenant isolation.

A Postgres view evaluates the underlying tables' RLS policies against the
**view owner** unless it is created `WITH (security_invoker = true)`. Migration
0004 creates `page_performance` as the migration role, which owns the tenant
tables — so without that setting the view would return every organisation's
rows to any caller, and would look entirely ordinary doing it.

That is the same shape as the cross-tenant leak this project already shipped
once (an app connected as superuser, RLS inert, the dashboard serving other
orgs' clients). A view is a second way to arrive at it, and the isolation suite
did not cover views at all.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from packages.db.engine import close_pool, init_pool, system_tx, tenant_tx


@pytest_asyncio.fixture(autouse=True)
async def engine_pool() -> AsyncIterator[None]:
    # init_pool defaults to the app role, so RLS genuinely applies here.
    await init_pool(min_size=1, max_size=2)
    try:
        yield
    finally:
        await close_pool()


@pytest_asyncio.fixture
async def two_sites_with_data(
    conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> AsyncIterator[dict[str, str]]:
    """One page of Search Console data in each org, on the same date and path."""
    for key in ("a", "b"):
        await conn.execute(
            """INSERT INTO gsc_daily (org_id, site_id, date, query, page, country,
                                      device, clicks, impressions, ctr, position)
               VALUES ($1, $2, current_date - 1, 'probe', $3, 'gbr', 'DESKTOP',
                       5, 100, 0.05, 4.0)""",
            two_orgs[f"org_{key}"],
            two_orgs[f"site_{key}"],
            f"https://{key}.example.com/shared-path",
        )
    yield two_orgs
    await conn.execute(
        "DELETE FROM gsc_daily WHERE query = 'probe' AND site_id = ANY($1::uuid[])",
        [two_orgs["site_a"], two_orgs["site_b"]],
    )


@pytest.mark.asyncio
async def test_view_shows_only_the_current_org(
    two_sites_with_data: dict[str, str],
) -> None:
    """The whole point of security_invoker."""
    async with tenant_tx(two_sites_with_data["org_a"], "owner") as conn:
        rows = await conn.fetch(
            "SELECT DISTINCT org_id FROM page_performance WHERE path = '/shared-path'"
        )

    org_ids = {str(r["org_id"]) for r in rows}
    assert org_ids == {two_sites_with_data["org_a"]}, (
        "the view leaked another organisation's rows — check that migration 0004 "
        "still creates it WITH (security_invoker = true)"
    )


@pytest.mark.asyncio
async def test_view_returns_nothing_without_tenant_context(
    two_sites_with_data: dict[str, str],
) -> None:
    """Same failure mode as a bare table read: empty, not everything."""
    async with system_tx() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM page_performance WHERE path = '/shared-path'"
        )
    assert count == 0


@pytest.mark.asyncio
async def test_security_invoker_is_actually_set() -> None:
    """Asserted directly, so a future migration that recreates the view without
    the option fails here rather than in production."""
    async with system_tx() as conn:
        options = await conn.fetchval(
            "SELECT reloptions FROM pg_class WHERE relname = 'page_performance'"
        )
    assert options and "security_invoker=true" in [o.replace(" ", "") for o in options]


# ── Path normalisation: the reason the join was impossible before ────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://acme.com/services", "/services"),
        # GSC and GA4 disagree about the trailing slash on the same page.
        ("https://acme.com/services/", "/services"),
        ("http://acme.com/a?utm_source=x", "/a"),
        ("https://acme.com/a#section", "/a"),
        ("https://acme.com", "/"),
        ("https://acme.com/", "/"),
        ("/", "/"),
        ("/already/a/path", "/already/a/path"),
        (None, None),
    ],
)
async def test_path_normalisation(raw: str | None, expected: str | None) -> None:
    async with system_tx() as conn:
        assert await conn.fetchval("SELECT seo_page_path($1)", raw) == expected


@pytest.mark.asyncio
async def test_full_outer_join_keeps_one_sided_pages(
    conn: asyncpg.Connection, two_orgs: dict[str, str]
) -> None:
    """A page with impressions and no sessions is a finding — nobody clicked.
    An inner join would silently drop it, which is the opposite of useful."""
    await conn.execute(
        """INSERT INTO gsc_daily (org_id, site_id, date, query, page, country,
                                  device, clicks, impressions, ctr, position)
           VALUES ($1, $2, current_date - 1, 'lonely', $3, 'gbr', 'DESKTOP',
                   0, 250, 0, 42.0)""",
        two_orgs["org_a"], two_orgs["site_a"], "https://a.example.com/no-clicks",
    )
    try:
        async with tenant_tx(two_orgs["org_a"], "owner") as tconn:
            row = await tconn.fetchrow(
                """SELECT impressions, sessions, in_search_console, in_analytics
                   FROM page_performance
                   WHERE site_id = $1 AND path = '/no-clicks'""",
                two_orgs["site_a"],
            )
        assert row is not None, "search-only page dropped by the join"
        assert row["impressions"] == 250
        assert row["sessions"] == 0
        assert row["in_search_console"] is True
        assert row["in_analytics"] is False
    finally:
        await conn.execute("DELETE FROM gsc_daily WHERE query = 'lonely'")
