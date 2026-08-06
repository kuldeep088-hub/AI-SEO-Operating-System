"""Expired auth rows are collected.

`oauth_states` and `sessions` only shed rows on the happy path — a consumed
callback, an explicit logout. Abandoned sign-ins and closed browsers leave rows
behind for good, and `/v1/auth/google/start` lets an unauthenticated caller
create the former at will.
"""

from __future__ import annotations

import os

import asyncpg
import pytest

from apps.worker.scheduler import sweep_expired


def _state() -> str:
    return f"test-{os.urandom(8).hex()}"


@pytest.mark.asyncio
async def test_expired_oauth_states_are_deleted(conn: asyncpg.Connection) -> None:
    stale, fresh = _state(), _state()
    await conn.execute(
        """INSERT INTO oauth_states (state, code_verifier, expires_at)
           VALUES ($1, '', now() - interval '1 hour'),
                  ($2, '', now() + interval '10 minutes')""",
        stale, fresh,
    )

    await sweep_expired(conn)

    assert not await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM oauth_states WHERE state = $1)", stale
    )
    assert await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM oauth_states WHERE state = $1)", fresh
    ), "an in-flight sign-in must survive the sweep"

    await conn.execute("DELETE FROM oauth_states WHERE state = ANY($1)", [stale, fresh])


@pytest.mark.asyncio
async def test_sweep_reports_what_it_deleted(conn: asyncpg.Connection) -> None:
    states = [_state() for _ in range(3)]
    for s in states:
        await conn.execute(
            """INSERT INTO oauth_states (state, code_verifier, expires_at)
               VALUES ($1, '', now() - interval '1 hour')""",
            s,
        )

    swept = await sweep_expired(conn)

    assert swept["oauth_states"] >= 3
    assert "sessions" in swept


@pytest.mark.asyncio
async def test_recently_expired_sessions_are_retained(conn: asyncpg.Connection) -> None:
    """Audit-log investigations join against sessions, so keep a 30-day tail."""
    org = await conn.fetchval(
        "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id",
        "Sweep Test", f"sweep-{os.urandom(4).hex()}",
    )
    user = await conn.fetchval(
        "INSERT INTO users (email) VALUES ($1) RETURNING id",
        f"sweep-{os.urandom(4).hex()}@example.com",
    )
    recent, ancient = os.urandom(16).hex(), os.urandom(16).hex()
    await conn.execute(
        """INSERT INTO sessions (token_hash, user_id, org_id, expires_at)
           VALUES ($1, $3, $4, now() - interval '2 days'),
                  ($2, $3, $4, now() - interval '90 days')""",
        recent, ancient, user, org,
    )

    await sweep_expired(conn)

    assert await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM sessions WHERE token_hash = $1)", recent
    ), "expired two days ago — still wanted for audit"
    assert not await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM sessions WHERE token_hash = $1)", ancient
    )

    await conn.execute("DELETE FROM organizations WHERE id = $1", org)
    await conn.execute("DELETE FROM users WHERE id = $1", user)
