"""Job runner — dequeue, lease, execute, retry.

The queue is the `jobs` table (docs/08-infrastructure.md §25). Workers hold a
lease rather than a lock, so a job whose worker was killed — Ctrl-C, OOM, laptop
lid closing at 02:15 — is reclaimed rather than stuck forever.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import asyncpg

from packages.core.errors import PermanentError, QuotaError
from packages.core.logging import get_logger
from packages.db.engine import pool

log = get_logger(__name__)

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
LEASE_MINUTES = 30
HEARTBEAT_SECONDS = 60
BACKOFF = [60, 300, 1800]  # 1 min, 5 min, 30 min

DEQUEUE = """
    UPDATE jobs
    SET    status = 'running',
           locked_by = $1,
           locked_at = now(),
           lease_expires_at = now() + ($3 || ' minutes')::interval,
           attempts = attempts + 1,
           started_at = COALESCE(started_at, now())
    WHERE  id = (
        SELECT id FROM jobs
        WHERE  status = 'queued' AND queue = $2 AND run_after <= now()
        ORDER  BY priority, run_after
        FOR UPDATE SKIP LOCKED
        LIMIT  1
    )
    RETURNING *
"""


async def dequeue(conn: asyncpg.Connection, queue: str) -> asyncpg.Record | None:
    return await conn.fetchrow(DEQUEUE, WORKER_ID, queue, str(LEASE_MINUTES))


async def reclaim_expired(conn: asyncpg.Connection) -> int:
    """Return jobs whose worker died to the queue."""
    result = await conn.execute(
        """
        UPDATE jobs
        SET    status = 'queued', locked_by = NULL, locked_at = NULL,
               lease_expires_at = NULL
        WHERE  status = 'running' AND lease_expires_at < now()
        """
    )
    n = int(result.split()[-1])
    if n:
        log.warning("jobs.reclaimed", count=n)
    return n


async def _heartbeat(job_id: str) -> None:
    """Extend the lease while a long job is legitimately still running."""
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            async with pool().acquire() as conn:
                await conn.execute(
                    """UPDATE jobs
                       SET lease_expires_at = now() + ($2 || ' minutes')::interval
                       WHERE id = $1 AND status = 'running'""",
                    job_id, str(LEASE_MINUTES),
                )
        except Exception:  # noqa: BLE001 — heartbeat must never kill the job
            log.warning("jobs.heartbeat_failed", job_id=job_id)


def make_progress(job_id: str) -> Callable[..., Awaitable[None]]:
    """Progress reporter, throttled to one write every 2 seconds."""
    last = {"t": 0.0}

    async def report(*, pct: int, detail: str = "") -> None:
        now = asyncio.get_event_loop().time()
        if now - last["t"] < 2.0 and pct < 100:
            return
        last["t"] = now
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET progress = $2::jsonb WHERE id = $1",
                job_id, json.dumps({"pct": pct, "detail": detail}),
            )

    return report


async def succeed(
    conn: asyncpg.Connection, job_id: str, result: dict[str, Any]
) -> None:
    await conn.execute(
        """UPDATE jobs
           SET status='succeeded', finished_at=now(), progress=$2::jsonb,
               locked_by=NULL, lease_expires_at=NULL, error=NULL
           WHERE id=$1""",
        job_id, json.dumps({"pct": 100, **{k: str(v) for k, v in result.items()}}),
    )


async def fail(conn: asyncpg.Connection, job: asyncpg.Record, exc: Exception) -> None:
    """Classify, then retry or dead-letter.

    Retrying a revoked OAuth token three times only delays telling the user
    something they must fix by hand — so PermanentError never retries, and a
    QuotaError does not consume an attempt.
    """
    message = str(exc)[:2000]

    if isinstance(exc, QuotaError):
        await conn.execute(
            """UPDATE jobs
               SET status='queued', run_after = now() + ($2 || ' seconds')::interval,
                   attempts = attempts - 1, error=$3, locked_by=NULL,
                   lease_expires_at=NULL
               WHERE id=$1""",
            job["id"], str(exc.retry_after), message,
        )
        log.warning("jobs.quota_paused", kind=job["kind"], retry_after=exc.retry_after)
        return

    permanent = isinstance(exc, PermanentError)
    if permanent or job["attempts"] >= job["max_attempts"]:
        await conn.execute(
            """UPDATE jobs SET status='dead', finished_at=now(), error=$2,
                   locked_by=NULL, lease_expires_at=NULL WHERE id=$1""",
            job["id"], message,
        )
        if job["org_id"]:
            await conn.execute(
                """INSERT INTO notifications (org_id, site_id, kind, title, body, severity)
                   VALUES ($1,$2,'job_failed',$3,$4,'warning')""",
                job["org_id"], job["site_id"],
                f"{job['kind']} failed", message[:500],
            )
        log.error("jobs.dead", kind=job["kind"], error=message, permanent=permanent)
        return

    delay = BACKOFF[min(job["attempts"] - 1, len(BACKOFF) - 1)]
    await conn.execute(
        """UPDATE jobs
           SET status='queued', run_after = now() + ($2 || ' seconds')::interval,
               error=$3, locked_by=NULL, lease_expires_at=NULL
           WHERE id=$1""",
        job["id"], str(delay), message,
    )
    log.warning("jobs.retry", kind=job["kind"], attempt=job["attempts"], delay=delay)


async def enqueue(
    conn: asyncpg.Connection,
    kind: str,
    *,
    org_id: str | None = None,
    site_id: str | None = None,
    queue: str = "default",
    priority: int = 100,
    **payload: Any,
) -> str | None:
    """Enqueue a job. Returns None when one is already pending for this site+kind.

    The partial unique index makes double-clicking "Sync now" a no-op rather
    than two concurrent syncs.

    The conflict is resolved by ON CONFLICT, not by catching the exception. A
    caught UniqueViolationError still leaves the surrounding transaction in an
    aborted state, so every later statement in it fails — which would mean one
    site with a pending job silently cancels the whole scheduler tick, and a
    double-clicked "Connect" aborts the tenant transaction that created the
    site. ON CONFLICT never raises, so the caller's transaction survives.
    """
    result: str | None = await conn.fetchval(
        """INSERT INTO jobs (org_id, site_id, kind, queue, priority, payload)
           VALUES ($1,$2,$3,$4,$5,$6::jsonb)
           ON CONFLICT (site_id, kind) WHERE status IN ('queued','running')
               DO NOTHING
           RETURNING id""",
        org_id, site_id, kind, queue, priority, json.dumps(payload),
    )
    if result is None:
        log.info("jobs.already_queued", kind=kind, site_id=site_id)
    return result


def utcnow() -> datetime:
    return datetime.now(UTC)
