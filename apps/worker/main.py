"""Worker pool.

Queue allocation follows docs/08-infrastructure.md §24. The `ai` queue gets
exactly one worker on purpose: one Ollama instance, one GPU — a second worker
halves each request's speed with no throughput gain.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from typing import Any

from apps.worker import runner, scheduler
from apps.worker.jobs import ga4_sync, gsc_sync, monthly_report
from packages.core.config import settings
from packages.core.logging import configure_logging, get_logger
from packages.db.engine import close_pool, init_pool, pool

configure_logging()
log = get_logger(__name__)

QUEUES = {
    "sync": 2,      # network-bound; Google quota is the limit
    "crawl": 4,     # network-bound
    "ai": 1,        # GPU-bound — Ollama is the bottleneck
    "report": 1,
    "default": 2,
}

HANDLERS: dict[str, Any] = {
    "gsc_sync": lambda conn, job, progress: gsc_sync.run(
        conn, site_id=str(job["site_id"]),
        backfill=job["payload"].get("backfill", False), progress=progress),
    "gsc_backfill": lambda conn, job, progress: gsc_sync.run(
        conn, site_id=str(job["site_id"]), backfill=True, progress=progress),
    "ga4_sync": lambda conn, job, progress: ga4_sync.run(
        conn, site_id=str(job["site_id"]),
        backfill=job["payload"].get("backfill", False), progress=progress),
    "ga4_backfill": lambda conn, job, progress: ga4_sync.run(
        conn, site_id=str(job["site_id"]), backfill=True, progress=progress),
    "refresh_views": lambda conn, job, progress: refresh_views(conn),
    # Queue "report": one at a time. The Report Narrator runs with reasoning
    # on, so it holds the GPU far longer than a structured call.
    "monthly_report": lambda conn, job, progress: monthly_report.run(
        conn, org_id=str(job["org_id"]), site_id=str(job["site_id"]),
        period_start=job["payload"].get("period_start"),
        period_end=job["payload"].get("period_end"),
        progress=progress),
}

_shutdown = asyncio.Event()


async def refresh_views(conn) -> dict:  # noqa: ANN001
    """Materialised views are refreshed after sync, never on a page request."""
    for view in ("mv_site_kpis", "mv_query_opportunities"):
        try:
            await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
        except Exception:  # noqa: BLE001 — CONCURRENTLY needs a populated view
            await conn.execute(f"REFRESH MATERIALIZED VIEW {view}")
    return {"refreshed": 2}


async def _run_job(job) -> None:  # noqa: ANN001
    import json

    handler = HANDLERS.get(job["kind"])
    job = dict(job)
    if isinstance(job["payload"], str):
        job["payload"] = json.loads(job["payload"])

    if handler is None:
        async with pool().acquire() as conn:
            await conn.execute(
                "UPDATE jobs SET status='dead', error=$2, finished_at=now() WHERE id=$1",
                job["id"], f"no handler for kind '{job['kind']}'",
            )
        return

    progress = runner.make_progress(str(job["id"]))
    beat = asyncio.create_task(runner._heartbeat(str(job["id"])))
    try:
        async with pool().acquire() as conn:
            result = await handler(conn, job, progress)
            await runner.succeed(conn, str(job["id"]), result or {})
        log.info("job.done", kind=job["kind"], job_id=str(job["id"]))

        # Chain: refresh the views once a sync lands new data.
        if job["kind"].startswith(("gsc_", "ga4_")):
            async with pool().acquire() as conn:
                await runner.enqueue(conn, "refresh_views", org_id=job["org_id"])
    except Exception as exc:  # noqa: BLE001 — classified in fail()
        log.exception("job.failed", kind=job["kind"], job_id=str(job["id"]))
        async with pool().acquire() as conn:
            await runner.fail(conn, job, exc)
    finally:
        beat.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await beat


async def _worker(queue: str, index: int) -> None:
    log.info("worker.started", queue=queue, index=index)
    while not _shutdown.is_set():
        try:
            async with pool().acquire() as conn:
                job = await runner.dequeue(conn, queue)
            if job is None:
                await asyncio.sleep(2)
                continue
            await _run_job(job)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — a worker must never die
            log.exception("worker.error", queue=queue)
            await asyncio.sleep(5)


async def _reclaimer() -> None:
    while not _shutdown.is_set():
        try:
            async with pool().acquire() as conn:
                await runner.reclaim_expired(conn)
        except Exception:  # noqa: BLE001
            log.exception("reclaimer.error")
        await asyncio.sleep(60)


async def _scheduler() -> None:
    """Evaluate cron schedules once a minute.

    Every worker process runs this; the advisory lock in `tick` means only one
    of them actually does the work on any given pass.
    """
    while not _shutdown.is_set():
        try:
            async with pool().acquire() as conn:
                n = await scheduler.tick(conn)
            if n:
                log.info("scheduler.enqueued", count=n)
        except Exception:  # noqa: BLE001 — a bad schedule must not kill the loop
            log.exception("scheduler.error")
        await asyncio.sleep(60)


async def main() -> None:
    # Privileged, unlike the API's pool. Claiming jobs and scanning due
    # schedules are cross-tenant by construction; under the RLS-scoped app role
    # both return zero rows and the queue quietly stops. Handlers must still
    # enter tenant_tx() before touching tenant data.
    await init_pool(min_size=2, max_size=12, dsn=settings.worker_database_url)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown.set)

    tasks = [asyncio.create_task(_reclaimer()), asyncio.create_task(_scheduler())]
    for queue, count in QUEUES.items():
        for i in range(count):
            tasks.append(asyncio.create_task(_worker(queue, i)))

    log.info("worker.pool_started", queues=QUEUES)
    await _shutdown.wait()
    log.info("worker.stopping")

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
