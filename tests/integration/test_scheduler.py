"""Scheduler properties from docs/08-infrastructure.md §24.

A scheduler that "works" is easy: fire the due rows. The properties that are
easy to lose — and that this suite exists to hold — are staggering, single
evaluation under concurrency, and no catch-up storm after downtime.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from apps.worker.runner import enqueue
from apps.worker.scheduler import (
    NIGHTLY_CRON,
    STAGGER_WINDOW_MINUTES,
    ensure_site_schedules,
    next_run,
    stagger_minutes,
    tick,
)

# asyncio_mode = "auto" handles the async tests; marking the sync ones warns.


# ── Pure logic: staggering ───────────────────────────────────────────────────


def test_stagger_is_deterministic() -> None:
    """Same site, same slot — every night. Otherwise nightly runs wander."""
    site = str(uuid.uuid4())
    assert stagger_minutes(site) == stagger_minutes(site)
    assert stagger_minutes(site) == stagger_minutes(uuid.UUID(site))


def test_stagger_stays_inside_the_window() -> None:
    for _ in range(200):
        assert 0 <= stagger_minutes(str(uuid.uuid4())) < STAGGER_WINDOW_MINUTES


def test_stagger_actually_spreads_sites() -> None:
    """The point of the offset is that 15 sites do not all fire at 02:00."""
    offsets = {stagger_minutes(str(uuid.uuid4())) for _ in range(15)}
    assert len(offsets) >= 12, "sites are clustering instead of spreading"


def test_next_run_applies_the_offset() -> None:
    site = str(uuid.uuid4())
    plain = next_run(NIGHTLY_CRON, "Asia/Kolkata")
    staggered = next_run(NIGHTLY_CRON, "Asia/Kolkata", site_id=site)
    assert (staggered - plain) == timedelta(minutes=stagger_minutes(site))


def test_next_run_is_always_in_the_future() -> None:
    """Three days of downtime must not produce a next_run_at in the past."""
    stale = datetime.now(UTC) - timedelta(days=3)
    assert next_run(NIGHTLY_CRON, "Asia/Kolkata", after=stale) > stale
    assert next_run(NIGHTLY_CRON, "Asia/Kolkata") > datetime.now(UTC)


def test_next_run_is_evaluated_in_the_schedule_timezone() -> None:
    """02:00 means 02:00 locally — Kolkata and UTC must not coincide."""
    kolkata = next_run(NIGHTLY_CRON, "Asia/Kolkata")
    utc = next_run(NIGHTLY_CRON, "UTC")
    assert kolkata.hour != utc.hour


# ── Against a real database ─────────────────────────────────────────────────


@pytest.fixture
async def site(conn: asyncpg.Connection):  # noqa: ANN201
    org = await conn.fetchval(
        "INSERT INTO organizations (name, slug) VALUES ($1,$2) RETURNING id",
        "Sched Test", f"sched-{uuid.uuid4().hex[:8]}",
    )
    client = await conn.fetchval(
        "INSERT INTO clients (org_id, name) VALUES ($1,$2) RETURNING id", org, "C"
    )
    site_id = await conn.fetchval(
        """INSERT INTO sites (org_id, client_id, domain, start_url, is_primary)
           VALUES ($1,$2,$3,$4,true) RETURNING id""",
        org, client, f"{uuid.uuid4().hex[:8]}.example.com",
        "https://example.com/",
    )
    yield {"org_id": str(org), "site_id": str(site_id)}
    await conn.execute("DELETE FROM organizations WHERE id = $1", org)


async def test_ensure_site_schedules_is_idempotent(
    conn: asyncpg.Connection, site: dict
) -> None:
    """Reconnecting a site must not double its nightly syncs."""
    first = await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=True
    )
    second = await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=True
    )
    assert sorted(first) == ["ga4_sync", "gsc_sync"]
    assert second == []

    count = await conn.fetchval(
        "SELECT count(*) FROM schedules WHERE site_id = $1", site["site_id"]
    )
    assert count == 2


async def test_only_connected_properties_are_scheduled(
    conn: asyncpg.Connection, site: dict
) -> None:
    """A ga4_sync on a site with no GA4 property would fail nightly, forever."""
    created = await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    assert created == ["gsc_sync"]

    kinds = await conn.fetch(
        "SELECT kind FROM schedules WHERE site_id = $1", site["site_id"]
    )
    assert [r["kind"] for r in kinds] == ["gsc_sync"]


async def test_a_schedule_gained_later_is_added_without_touching_the_first(
    conn: asyncpg.Connection, site: dict
) -> None:
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    original = await conn.fetchval(
        "SELECT next_run_at FROM schedules WHERE site_id=$1 AND kind='gsc_sync'",
        site["site_id"],
    )
    created = await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=True
    )
    assert created == ["ga4_sync"]

    unchanged = await conn.fetchval(
        "SELECT next_run_at FROM schedules WHERE site_id=$1 AND kind='gsc_sync'",
        site["site_id"],
    )
    assert unchanged == original


async def test_tick_does_not_fire_a_freshly_created_schedule(
    conn: asyncpg.Connection, site: dict
) -> None:
    """next_run_at is set on creation, so the site is not synced twice at once
    — the backfill enqueued by /connect is already running."""
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    await tick(conn)
    jobs = await conn.fetchval(
        "SELECT count(*) FROM jobs WHERE site_id = $1", site["site_id"]
    )
    assert jobs == 0


async def test_tick_fires_a_due_schedule_onto_the_right_queue(
    conn: asyncpg.Connection, site: dict
) -> None:
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    await conn.execute(
        "UPDATE schedules SET next_run_at = now() - interval '1 minute' WHERE site_id=$1",
        site["site_id"],
    )

    assert await tick(conn) == 1

    job = await conn.fetchrow(
        "SELECT kind, queue, priority, status FROM jobs WHERE site_id = $1",
        site["site_id"],
    )
    assert job["kind"] == "gsc_sync"
    assert job["queue"] == "sync"
    # Scheduled work is priority 100 so a user's "Sync now" (50) jumps it.
    assert job["priority"] == 100
    assert job["status"] == "queued"


async def test_downtime_produces_one_run_not_a_storm(
    conn: asyncpg.Connection, site: dict
) -> None:
    """Laptop closed for three days: one catch-up sync, then forward."""
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    await conn.execute(
        "UPDATE schedules SET next_run_at = now() - interval '3 days' WHERE site_id=$1",
        site["site_id"],
    )

    assert await tick(conn) == 1
    assert await tick(conn) == 0, "second tick re-fired — next_run_at did not advance"

    nxt = await conn.fetchval(
        "SELECT next_run_at FROM schedules WHERE site_id = $1", site["site_id"]
    )
    assert nxt > datetime.now(UTC)

    total = await conn.fetchval(
        "SELECT count(*) FROM jobs WHERE site_id = $1", site["site_id"]
    )
    assert total == 1


async def test_tick_advances_even_when_a_job_is_already_pending(
    conn: asyncpg.Connection, site: dict
) -> None:
    """The partial unique index makes enqueue a no-op. If next_run_at did not
    advance anyway, the schedule stays due and the tick loop spins forever."""
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    await conn.execute(
        """INSERT INTO jobs (org_id, site_id, kind, queue, status)
           VALUES ($1,$2,'gsc_sync','sync','queued')""",
        site["org_id"], site["site_id"],
    )
    await conn.execute(
        "UPDATE schedules SET next_run_at = now() - interval '1 minute' WHERE site_id=$1",
        site["site_id"],
    )

    assert await tick(conn) == 0  # blocked by the unique index

    nxt = await conn.fetchval(
        "SELECT next_run_at FROM schedules WHERE site_id = $1", site["site_id"]
    )
    assert nxt > datetime.now(UTC), "schedule stayed due — tick loop would spin"


async def test_a_duplicate_enqueue_does_not_poison_the_transaction(
    conn: asyncpg.Connection, site: dict
) -> None:
    """A rejected duplicate must be a no-op, not an aborted transaction.

    Postgres aborts the whole block on a constraint violation, so catching the
    exception is not enough — the next statement fails too. That would let one
    site with a pending job silently cancel every other site's nightly sync.
    """
    async with conn.transaction():
        first = await enqueue(
            conn, "gsc_sync", org_id=site["org_id"], site_id=site["site_id"],
            queue="sync",
        )
        assert first is not None

        duplicate = await enqueue(
            conn, "gsc_sync", org_id=site["org_id"], site_id=site["site_id"],
            queue="sync",
        )
        assert duplicate is None

        # The transaction must still be usable after the rejected duplicate.
        assert await conn.fetchval("SELECT 1") == 1
        other = await enqueue(
            conn, "ga4_sync", org_id=site["org_id"], site_id=site["site_id"],
            queue="sync",
        )
        assert other is not None, "later work in the same transaction was lost"


async def test_one_blocked_site_does_not_cancel_the_whole_tick(
    conn: asyncpg.Connection, site: dict
) -> None:
    """Site A already syncing must not stop site B's nightly job being queued."""
    other_site = await conn.fetchval(
        """INSERT INTO sites (org_id, client_id, domain, start_url, is_primary)
           SELECT org_id, client_id, $2, 'https://b.example.com/', false
           FROM sites WHERE id = $1 RETURNING id""",
        site["site_id"], f"{uuid.uuid4().hex[:8]}.example.com",
    )
    for sid in (site["site_id"], str(other_site)):
        await ensure_site_schedules(
            conn, org_id=site["org_id"], site_id=sid, gsc=True, ga4=False
        )
    # Site A is already mid-sync — its enqueue will be rejected.
    await conn.execute(
        """INSERT INTO jobs (org_id, site_id, kind, queue, status)
           VALUES ($1,$2,'gsc_sync','sync','running')""",
        site["org_id"], site["site_id"],
    )
    await conn.execute("UPDATE schedules SET next_run_at = now() - interval '1 minute'")

    assert await tick(conn) == 1  # site B got through

    queued = await conn.fetchval(
        "SELECT count(*) FROM jobs WHERE site_id = $1 AND status = 'queued'",
        other_site,
    )
    assert queued == 1, "a blocked site cancelled the rest of the tick"


async def test_inactive_schedules_never_fire(
    conn: asyncpg.Connection, site: dict
) -> None:
    await ensure_site_schedules(
        conn, org_id=site["org_id"], site_id=site["site_id"], gsc=True, ga4=False
    )
    await conn.execute(
        """UPDATE schedules SET is_active = false,
               next_run_at = now() - interval '1 day' WHERE site_id = $1""",
        site["site_id"],
    )
    assert await tick(conn) == 0


async def test_only_one_worker_evaluates_a_tick(site: dict) -> None:
    """Two workers, one due schedule, one job — not two.

    The advisory lock is the whole defence here. Without it every worker in the
    pool enqueues the nightly sync.
    """
    # The privileged URL, matching how the worker actually connects: the
    # scheduler scans every org's schedules in one pass, so it cannot run under
    # a tenant-scoped RLS context. See settings.worker_database_url.
    from tests.conftest import ADMIN_DATABASE_URL

    a = await asyncpg.connect(ADMIN_DATABASE_URL)
    b = await asyncpg.connect(ADMIN_DATABASE_URL)
    try:
        await a.execute(
            """INSERT INTO schedules (org_id, site_id, kind, cron, timezone, next_run_at)
               VALUES ($1,$2,'gsc_sync','0 2 * * *','Asia/Kolkata',
                       now() - interval '1 minute')""",
            site["org_id"], site["site_id"],
        )

        # b holds the lock; a must decline rather than double-enqueue.
        async with b.transaction():
            assert await b.fetchval("SELECT pg_try_advisory_xact_lock(4815162342)")
            assert await tick(a) == 0

        assert await tick(a) == 1

        total = await a.fetchval(
            "SELECT count(*) FROM jobs WHERE site_id = $1", site["site_id"]
        )
        assert total == 1
    finally:
        await a.close()
        await b.close()
