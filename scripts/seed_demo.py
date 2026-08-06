#!/usr/bin/env python
"""Demo data so you can look around before Google OAuth is configured.

    python scripts/seed_demo.py          # create, print a sign-in URL
    python scripts/seed_demo.py --clear  # remove everything it created

This is fake data in your real database. Clear it before connecting a real
client — see docs/12-roadmap.md §49.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta

import asyncpg

DEMO_SLUG = "seoos-demo"


async def clear(conn: asyncpg.Connection) -> None:
    n = await conn.fetchval(
        "DELETE FROM organizations WHERE slug = $1 RETURNING 1", DEMO_SLUG
    )
    await conn.execute(
        "DELETE FROM users WHERE email = 'demo@example.com'"
    )
    print("demo data removed" if n else "no demo data found")


async def seed(conn: asyncpg.Connection) -> str:
    await clear(conn)

    org = await conn.fetchval(
        "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id",
        "Demo Agency", DEMO_SLUG,
    )
    user = await conn.fetchval(
        "INSERT INTO users (email, name) VALUES ($1, $2) RETURNING id",
        "demo@example.com", "Demo User",
    )
    await conn.execute(
        "INSERT INTO memberships (org_id, user_id, role) VALUES ($1, $2, 'owner')",
        org, user,
    )

    # (client, industry, domain, criticals, base impressions/day, base clicks/day,
    #  trend) — trend shapes the 28d-vs-previous-28d delta the dashboard shows.
    fixtures = [
        ("Acme Corporation", "Refrigeration", "acme.com", 14, 1400, 42, -0.22),
        ("Nova Systems", "SaaS", "novasystems.io", 0, 620, 18, 0.31),
        ("Vertex Retail", "E-commerce", "vertexretail.in", 2, 2100, 88, 0.06),
        ("Blue Ridge Cafes", "Hospitality", "blueridgecafes.com", 0, 380, 14, 0.12),
        ("Kalyan Enterprises", "Manufacturing", "kalyanent.in", 0, 210, 6, -0.04),
    ]
    for name, industry, domain, criticals, impressions, clicks, trend in fixtures:
        client = await conn.fetchval(
            "INSERT INTO clients (org_id, name, industry) VALUES ($1,$2,$3) RETURNING id",
            org, name, industry,
        )
        site = await conn.fetchval(
            """INSERT INTO sites (org_id, client_id, domain, start_url, is_primary)
               VALUES ($1,$2,$3,$4,true) RETURNING id""",
            org, client, domain, f"https://{domain}/",
        )
        if criticals:
            await conn.execute(
                """INSERT INTO issues (org_id, site_id, rule_key, severity, affected_count)
                   VALUES ($1,$2,'http.404','critical',$3)""",
                org, site, criticals,
            )
        # 56 days: the most recent 28 carry the trend, the prior 28 are the
        # baseline the dashboard compares against. Deterministic wobble so the
        # numbers look like traffic rather than a straight line.
        await conn.execute(
            """INSERT INTO gsc_daily (org_id, site_id, date, query, page,
                                      clicks, impressions, ctr, position)
               SELECT $1, $2,
                      current_date - (n || ' days')::interval,
                      q.query, $3,
                      GREATEST(0, round($4 * q.share
                          * (CASE WHEN n <= 28 THEN 1 + $6::float8 ELSE 1 END)
                          * (1 + 0.18 * sin(n * 0.7))))::int,
                      GREATEST(0, round($5 * q.share
                          * (CASE WHEN n <= 28 THEN 1 + $6::float8 * 0.4 ELSE 1 END)
                          * (1 + 0.15 * cos(n * 0.5))))::int,
                      0.048, 4.0 + q.pos
               FROM generate_series(1, 56) n
               CROSS JOIN (VALUES
                   ('commercial fridge repair', 0.42, 0.2),
                   ('walk-in cooler price',     0.28, 1.4),
                   ('refrigeration servicing',  0.18, 7.1),
                   ('fridge maintenance cost',  0.12, 10.6)
               ) AS q(query, share, pos)""",
            org, site, f"https://{domain}/services", clicks, impressions, trend,
        )

    await conn.execute("REFRESH MATERIALIZED VIEW mv_site_kpis")

    token = secrets.token_urlsafe(32)
    await conn.execute(
        """INSERT INTO sessions (token_hash, user_id, org_id, expires_at)
           VALUES ($1,$2,$3,$4)""",
        hashlib.sha256(token.encode()).hexdigest(), user, org,
        datetime.now(UTC) + timedelta(days=7),
    )
    return token


async def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set — run: set -a; source .env; set +a")

    conn = await asyncpg.connect(url)
    try:
        if "--clear" in sys.argv:
            await clear(conn)
            return
        token = await seed(conn)
    finally:
        await conn.close()

    print("\n  Demo data created: 3 clients, 3 sites, 28 days of GSC rows.\n")
    print("  \033[1mOpen this link:\033[0m\n")
    print(f"    http://localhost:3000/demo?t={token}\n")
    print("  It sets the session cookie and redirects to the dashboard.")
    print("  Valid 7 days. Demo organisation only — it cannot sign in a real user.\n")
    print("  Remove everything:  uv run python scripts/seed_demo.py --clear\n")


if __name__ == "__main__":
    asyncio.run(main())
