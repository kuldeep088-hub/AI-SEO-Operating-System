"""Job progress — docs/12-roadmap.md Phase 1 week 4, "progress SSE".

Handlers already write `jobs.progress` as they work; nothing carried it to the
browser, so connecting a site started a 16-month backfill and then showed a
static page for several minutes with no indication anything was happening.

Server-sent events rather than websockets: the traffic is one-directional, SSE
is a plain HTTP response that the existing Caddy config already proxies, and
the browser reconnects on its own. A websocket would need connection
management for no gain.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from apps.api.deps import CurrentPrincipal
from packages.core.logging import get_logger
from packages.db.engine import tenant_tx

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
log = get_logger(__name__)

POLL_SECONDS = 1.5

# A backfill can legitimately run for a long time, but a stream is not a
# subscription — the browser reconnects by itself, so capping the connection
# bounds how long a forgotten tab holds a worker.
MAX_STREAM_SECONDS = 900

TERMINAL = {"succeeded", "failed", "dead", "cancelled"}


async def _snapshot(org_id: str, role: str, site_id: str) -> list[dict[str, Any]]:
    async with tenant_tx(org_id, role) as conn:
        rows = await conn.fetch(
            """SELECT id, kind, status, progress, error,
                      created_at, started_at, finished_at
               FROM   jobs
               WHERE  site_id = $1 AND created_at > now() - interval '2 hours'
               ORDER  BY created_at DESC LIMIT 20""",
            site_id,
        )
    out = []
    for r in rows:
        progress = r["progress"]
        if isinstance(progress, str):
            progress = json.loads(progress)
        out.append(
            {
                "id": str(r["id"]),
                "kind": r["kind"],
                "status": r["status"],
                "pct": (progress or {}).get("pct"),
                "detail": (progress or {}).get("detail"),
                "error": r["error"],
                "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            }
        )
    return out


@router.get("/stream/{site_id}")
async def stream(
    site_id: str,
    request: Request,
    principal: CurrentPrincipal,
) -> StreamingResponse:
    """Live job state for one site, as server-sent events."""

    async def events() -> AsyncIterator[str]:
        elapsed = 0.0
        last_payload: str | None = None

        # Send immediately so the client renders current state rather than
        # waiting a poll interval to discover a job is already finished.
        try:
            while elapsed < MAX_STREAM_SECONDS:
                # Checked every loop: without it a closed tab leaves this
                # polling the database until MAX_STREAM_SECONDS expires.
                if await request.is_disconnected():
                    break

                jobs = await _snapshot(principal.org_id, principal.role, site_id)
                payload = json.dumps({"jobs": jobs})

                # Only push on change. A backfill that sits at 40% for a minute
                # should not send forty identical frames.
                if payload != last_payload:
                    last_payload = payload
                    yield f"event: jobs\ndata: {payload}\n\n"

                if jobs and all(j["status"] in TERMINAL for j in jobs):
                    yield 'event: done\ndata: {"reason":"all jobs finished"}\n\n'
                    break

                await asyncio.sleep(POLL_SECONDS)
                elapsed += POLL_SECONDS
            else:
                # Distinguishable from `done` so the client knows to reconnect
                # rather than assume the work completed.
                yield 'event: timeout\ndata: {"reason":"stream age limit"}\n\n'
        except asyncio.CancelledError:
            # Normal on disconnect; not worth an error log.
            raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            # Caddy does not buffer by default, but an intermediate proxy that
            # does would hold every frame until the stream ended, which looks
            # exactly like the bug this endpoint exists to fix.
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
