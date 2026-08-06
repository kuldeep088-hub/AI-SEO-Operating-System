"""Recurring job scheduler — docs/08-infrastructure.md §24.

`schedules` holds cron expressions. Every worker process ticks, but a single-row
advisory lock means exactly one of them evaluates any given tick, so N workers
do not enqueue N copies of the nightly sync.

Two properties this file exists to preserve:

1. **Staggering.** Fifteen sites all firing at 02:00 saturate the connection and
   get the IP throttled by Google. The offset is derived from the site UUID, so
   a site lands in the same slot every night — stable, debuggable, and spread
   across a 4-hour window.
2. **No catch-up storm.** A laptop that was closed for three days must run each
   schedule *once* on wake, not three times. `next_run_at` is always recomputed
   forward from `now()`, never from the stale value.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
from croniter import croniter

from apps.worker.runner import enqueue
from packages.core.logging import get_logger

log = get_logger(__name__)

# One arbitrary but fixed key, so every worker contends for the same lock.
TICK_LOCK = 4815162342

# Spread nightly work across four hours.
STAGGER_WINDOW_MINUTES = 240

# Where each scheduled kind runs, and at what priority. Scheduled work is
# priority 100; user-triggered work is 50 and therefore jumps the queue (§25).
QUEUE_FOR: dict[str, str] = {
    "gsc_sync": "sync",
    "ga4_sync": "sync",
    "refresh_views": "default",
    # Its own queue, concurrency 1: the narrative call holds the GPU, and two
    # reports generating at once would contend for it.
    "monthly_report": "report",
}
SCHEDULED_PRIORITY = 100

# Nightly at 02:00 local, before anyone looks at a dashboard.
NIGHTLY_CRON = "0 2 * * *"

# Monthly report on the 3rd at 04:00 local. The 3rd rather than the 1st because
# Search Console finalises data with a ~3 day lag — a report generated at
# midnight on the 1st would under-report the last days of the month it covers
# and never correct itself. 04:00 rather than 02:00 so the nightly syncs, and
# the view refresh they chain, have landed first.
MONTHLY_REPORT_CRON = "0 4 3 * *"
DEFAULT_TZ = "Asia/Kolkata"


def stagger_minutes(site_id: str | uuid.UUID | None) -> int:
    """Deterministic per-site offset within the stagger window.

    Org-wide schedules (no site) get no offset — there is only one of them.
    """
    if site_id is None:
        return 0
    raw = site_id.bytes if isinstance(site_id, uuid.UUID) else uuid.UUID(str(site_id)).bytes
    digest = hashlib.sha256(raw).hexdigest()[:8]
    return int(digest, 16) % STAGGER_WINDOW_MINUTES


def next_run(
    cron: str,
    timezone: str,
    *,
    site_id: str | uuid.UUID | None = None,
    after: datetime | None = None,
) -> datetime:
    """The next firing time, in UTC, with the site's stagger applied.

    The cron expression is evaluated in the schedule's own timezone so that
    "02:00" means 02:00 in Kolkata across DST changes elsewhere, not 02:00 UTC.
    """
    tz = ZoneInfo(timezone)
    base = (after or datetime.now(UTC)).astimezone(tz)
    upcoming: datetime = croniter(cron, base).get_next(datetime)
    if upcoming.tzinfo is None:
        upcoming = upcoming.replace(tzinfo=tz)
    return upcoming.astimezone(UTC) + timedelta(minutes=stagger_minutes(site_id))


async def sweep_expired(conn: asyncpg.Connection) -> dict[str, int]:
    """Delete authentication rows that are past their expiry.

    Both tables only ever shed rows on the happy path: `oauth_states` is deleted
    when a callback consumes it, and sessions are revoked on explicit logout. An
    abandoned sign-in and a browser that never logs out both leave a row behind
    permanently.

    On localhost that is a rounding error. Once the app is public it is a table
    an unauthenticated caller can grow — `/v1/auth/google/start` inserts a state
    row before any credential is checked — so it needs a sweep, not just a rate
    limit.

    Sessions are kept for 30 days past expiry rather than deleted immediately,
    because `audit_log` investigations reference them.
    """
    states = await conn.execute("DELETE FROM oauth_states WHERE expires_at < now()")
    sessions = await conn.execute(
        "DELETE FROM sessions WHERE expires_at < now() - interval '30 days'"
    )
    swept = {
        "oauth_states": _rowcount(states),
        "sessions": _rowcount(sessions),
    }
    if any(swept.values()):
        log.info("scheduler.swept", **swept)
    return swept


def _rowcount(status: str) -> int:
    """asyncpg returns the raw command tag, e.g. 'DELETE 12'."""
    try:
        return int(status.rsplit(" ", 1)[-1])
    except (ValueError, AttributeError):
        return 0


async def tick(conn: asyncpg.Connection) -> int:
    """Evaluate due schedules once. Returns how many jobs were enqueued.

    Everything happens inside one transaction holding an advisory lock that is
    released on commit, so a crash mid-tick cannot leave the lock held.
    """
    enqueued = 0
    async with conn.transaction():
        if not await conn.fetchval("SELECT pg_try_advisory_xact_lock($1)", TICK_LOCK):
            return 0  # another worker owns this tick

        # Under the same lock, so exactly one worker sweeps per tick.
        await sweep_expired(conn)

        due = await conn.fetch(
            """
            SELECT id, org_id, site_id, kind, cron, timezone, payload, next_run_at
            FROM   schedules
            WHERE  is_active AND (next_run_at IS NULL OR next_run_at <= now())
            FOR UPDATE
            """
        )

        for s in due:
            # A NULL next_run_at means "never scheduled yet" — initialise it
            # rather than treating the schedule as overdue and firing at once.
            if s["next_run_at"] is not None:
                job_id = await enqueue(
                    conn,
                    s["kind"],
                    org_id=str(s["org_id"]),
                    site_id=str(s["site_id"]) if s["site_id"] else None,
                    queue=QUEUE_FOR.get(s["kind"], "default"),
                    priority=SCHEDULED_PRIORITY,
                    **_payload(s["payload"]),
                )
                if job_id:
                    enqueued += 1
                    log.info(
                        "schedule.fired",
                        kind=s["kind"],
                        site_id=str(s["site_id"]) if s["site_id"] else None,
                    )

            # Always advance, even when the enqueue was a no-op because a job
            # of that kind was still pending. Otherwise the schedule stays due
            # and the tick loop spins every second.
            await conn.execute(
                """UPDATE schedules
                   SET last_run_at = CASE WHEN $3 THEN now() ELSE last_run_at END,
                       next_run_at = $2
                   WHERE id = $1""",
                s["id"],
                next_run(s["cron"], s["timezone"], site_id=s["site_id"]),
                s["next_run_at"] is not None,
            )

    return enqueued


def _payload(raw: object) -> dict[str, Any]:
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    return raw if isinstance(raw, dict) else {}


async def ensure_site_schedules(
    conn: asyncpg.Connection,
    *,
    org_id: str,
    site_id: str,
    gsc: bool,
    ga4: bool,
    timezone: str = DEFAULT_TZ,
) -> list[str]:
    """Create the nightly schedules a newly connected site needs.

    Idempotent: reconnecting a site does not double its schedules, and a site
    that gains GA4 later gets the GA4 schedule added without touching the GSC
    one. Only kinds whose property is actually connected are scheduled — a
    `ga4_sync` on a site with no GA4 property would fail nightly, forever.
    """
    wanted = [k for k, on in (("gsc_sync", gsc), ("ga4_sync", ga4)) if on]
    # A monthly report needs Search Console; GA4 alone has nothing to narrate.
    if gsc:
        wanted.append("monthly_report")
    created: list[str] = []

    for kind in wanted:
        cron = MONTHLY_REPORT_CRON if kind == "monthly_report" else NIGHTLY_CRON
        row = await conn.fetchval(
            """
            INSERT INTO schedules (org_id, site_id, kind, cron, timezone, next_run_at)
            SELECT $1, $2, $3, $4, $5, $6
            WHERE NOT EXISTS (
                SELECT 1 FROM schedules WHERE site_id = $2 AND kind = $3
            )
            RETURNING id
            """,
            org_id,
            site_id,
            kind,
            cron,
            timezone,
            next_run(cron, timezone, site_id=site_id),
        )
        if row:
            created.append(kind)

    if created:
        log.info(
            "schedules.created",
            site_id=site_id,
            kinds=created,
            stagger_minutes=stagger_minutes(site_id),
        )
    return created
