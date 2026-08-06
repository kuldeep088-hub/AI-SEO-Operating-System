"""Search Console sync — backfill and incremental.

The watermark is deliberately not "the newest date seen". GSC finalises data
with a ~3 day lag, so the sync re-pulls a rolling volatile window and upserts.
Tracking only the newest date would permanently under-report the last few days.
See docs/05-database.md §13.3.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import asyncpg

from packages.core.logging import get_logger
from packages.integrations.google import gsc
from packages.integrations.google.oauth import get_access_token

log = get_logger(__name__)

# Search Console retains 16 months. Asking for more returns nothing.
MAX_HISTORY_DAYS = 16 * 30

UPSERT = """
    INSERT INTO gsc_daily (org_id, site_id, date, query, page, country, device,
                           clicks, impressions, ctr, position)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
    ON CONFLICT (site_id, date, query, page, country, device) DO UPDATE
        SET clicks      = EXCLUDED.clicks,
            impressions = EXCLUDED.impressions,
            ctr         = EXCLUDED.ctr,
            position    = EXCLUDED.position
"""


async def run(conn: asyncpg.Connection, *, site_id: str, backfill: bool = False,
              progress=None) -> dict:
    site = await conn.fetchrow(
        "SELECT id, org_id, domain, gsc_property FROM sites WHERE id = $1", site_id
    )
    if site is None:
        return {"skipped": "site not found"}
    if not site["gsc_property"]:
        return {"skipped": "no Search Console property connected"}

    org_id = str(site["org_id"])
    token = await get_access_token(conn, org_id)

    state = await conn.fetchrow(
        "SELECT last_synced_date FROM sync_state WHERE site_id = $1 AND source = 'gsc'",
        site_id,
    )

    # GSC has no data for the last ~2 days; asking for it wastes a request.
    end = date.today() - timedelta(days=2)
    if backfill or state is None or state["last_synced_date"] is None:
        start = date.today() - timedelta(days=MAX_HISTORY_DAYS)
    else:
        # Re-pull the volatile window so late-arriving rows are corrected.
        start = state["last_synced_date"] - timedelta(days=gsc.VOLATILE_DAYS)

    if start > end:
        return {"skipped": "already current"}

    # Month-sized chunks: bounded memory, and a failure loses one month not sixteen.
    total = 0
    chunk_start = start
    months = max(1, ((end - start).days // 30) + 1)
    done = 0

    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=30), end)
        rows = await gsc.query_search_analytics(
            token, site["gsc_property"], chunk_start, chunk_end
        )
        tuples = gsc.to_daily_rows(rows, org_id=org_id, site_id=site_id)
        if tuples:
            await conn.executemany(UPSERT, tuples)
            total += len(tuples)

        done += 1
        if progress:
            await progress(
                pct=int(done / months * 100),
                detail=f"{chunk_start:%b %Y} — {total:,} rows",
            )

        chunk_start = chunk_end + timedelta(days=1)

    await conn.execute(
        """
        INSERT INTO sync_state (org_id, site_id, source, last_synced_date,
                                last_run_at, rows_ingested)
        VALUES ($1, $2, 'gsc', $3, now(), $4)
        ON CONFLICT (site_id, source) DO UPDATE
            SET last_synced_date = EXCLUDED.last_synced_date,
                last_run_at      = now(),
                last_error       = NULL,
                rows_ingested    = sync_state.rows_ingested + EXCLUDED.rows_ingested
        """,
        org_id, site_id, end, total,
    )

    log.info("gsc_sync.done", site=site["domain"], rows=total,
             start=str(start), end=str(end))
    return {"rows": total, "from": str(start), "to": str(end)}


async def mark_error(conn: asyncpg.Connection, site_id: str, message: str) -> None:
    await conn.execute(
        """
        INSERT INTO sync_state (org_id, site_id, source, last_run_at, last_error)
        SELECT org_id, id, 'gsc', now(), $2 FROM sites WHERE id = $1
        ON CONFLICT (site_id, source) DO UPDATE
            SET last_run_at = now(), last_error = EXCLUDED.last_error
        """,
        site_id, message[:500],
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
