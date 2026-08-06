"""GA4 sync — same watermark pattern as Search Console.

GA4 also revises recent data (attribution settles over a few days), so the same
rolling volatile window applies.
"""

from __future__ import annotations

from datetime import date, timedelta

import asyncpg

from packages.core.logging import get_logger
from packages.integrations.google import ga4
from packages.integrations.google.oauth import get_access_token

log = get_logger(__name__)

MAX_HISTORY_DAYS = 16 * 30
VOLATILE_DAYS = 3

UPSERT = """
    INSERT INTO ga4_daily (org_id, site_id, date, landing_page, channel,
                           sessions, engaged_sessions, conversions, revenue)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
    ON CONFLICT (site_id, date, landing_page, channel) DO UPDATE
        SET sessions         = EXCLUDED.sessions,
            engaged_sessions = EXCLUDED.engaged_sessions,
            conversions      = EXCLUDED.conversions,
            revenue          = EXCLUDED.revenue
"""


async def run(conn: asyncpg.Connection, *, site_id: str, backfill: bool = False,
              progress=None) -> dict:
    site = await conn.fetchrow(
        "SELECT id, org_id, domain, ga4_property_id FROM sites WHERE id = $1", site_id
    )
    if site is None:
        return {"skipped": "site not found"}
    if not site["ga4_property_id"]:
        return {"skipped": "no GA4 property connected"}

    org_id = str(site["org_id"])
    token = await get_access_token(conn, org_id)

    state = await conn.fetchrow(
        "SELECT last_synced_date FROM sync_state WHERE site_id = $1 AND source = 'ga4'",
        site_id,
    )

    end = date.today() - timedelta(days=1)
    if backfill or state is None or state["last_synced_date"] is None:
        start = date.today() - timedelta(days=MAX_HISTORY_DAYS)
    else:
        start = state["last_synced_date"] - timedelta(days=VOLATILE_DAYS)

    if start > end:
        return {"skipped": "already current"}

    total = 0
    chunk_start = start
    months = max(1, ((end - start).days // 60) + 1)
    done = 0

    # GA4 quota is token-based, so fewer, wider requests are cheaper than many
    # narrow ones — 60-day chunks rather than GSC's 30.
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=60), end)
        rows = await ga4.run_report(
            token, site["ga4_property_id"], chunk_start, chunk_end
        )
        tuples = ga4.to_daily_rows(rows, org_id=org_id, site_id=site_id)
        if tuples:
            await conn.executemany(UPSERT, tuples)
            total += len(tuples)

        done += 1
        if progress:
            await progress(pct=int(done / months * 100),
                           detail=f"{chunk_start:%b %Y} — {total:,} rows")

        chunk_start = chunk_end + timedelta(days=1)

    await conn.execute(
        """
        INSERT INTO sync_state (org_id, site_id, source, last_synced_date,
                                last_run_at, rows_ingested)
        VALUES ($1, $2, 'ga4', $3, now(), $4)
        ON CONFLICT (site_id, source) DO UPDATE
            SET last_synced_date = EXCLUDED.last_synced_date,
                last_run_at      = now(),
                last_error       = NULL,
                rows_ingested    = sync_state.rows_ingested + EXCLUDED.rows_ingested
        """,
        org_id, site_id, end, total,
    )

    log.info("ga4_sync.done", site=site["domain"], rows=total)
    return {"rows": total, "from": str(start), "to": str(end)}
