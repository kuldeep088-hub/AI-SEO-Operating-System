"""Regression tests for the user upsert in the OAuth callback.

The callback's ON CONFLICT target must match an actual constraint. It broke once
already: the schema enforces case-insensitive uniqueness with an expression
index on lower(email) — because the bundled Postgres has no citext — while the
callback still said ON CONFLICT (email). Nothing caught it until a real sign-in.
"""

from __future__ import annotations

import asyncpg
import pytest

UPSERT = """
    INSERT INTO users (email, name, avatar_url, google_sub, last_seen_at)
    VALUES ($1, $2, $3, $4, now())
    ON CONFLICT ((lower(email))) DO UPDATE
        SET name = EXCLUDED.name,
            avatar_url = EXCLUDED.avatar_url,
            google_sub = EXCLUDED.google_sub,
            last_seen_at = now()
    RETURNING id
"""


@pytest.fixture
async def cleanup_user(conn: asyncpg.Connection):
    yield
    await conn.execute("DELETE FROM users WHERE email ILIKE 'upsert-test%'")


async def test_upsert_creates_then_updates(
    conn: asyncpg.Connection, cleanup_user: None
) -> None:
    """The exact statement the callback runs must not raise, and must upsert."""
    first = await conn.fetchval(
        UPSERT, "upsert-test@example.com", "First", None, "sub-1"
    )
    second = await conn.fetchval(
        UPSERT, "upsert-test@example.com", "Second", None, "sub-1"
    )
    assert first == second, "second sign-in created a duplicate user"

    name = await conn.fetchval("SELECT name FROM users WHERE id = $1", first)
    assert name == "Second", "profile was not refreshed on re-sign-in"


async def test_upsert_is_case_insensitive(
    conn: asyncpg.Connection, cleanup_user: None
) -> None:
    """Google can return a differently-cased address; it must be the same user."""
    lower = await conn.fetchval(
        UPSERT, "upsert-test2@example.com", "Lower", None, "sub-2"
    )
    upper = await conn.fetchval(
        UPSERT, "UPSERT-Test2@Example.com", "Upper", None, "sub-2"
    )
    assert lower == upper, "case difference created a second account"


async def test_email_uniqueness_is_enforced(
    conn: asyncpg.Connection, cleanup_user: None
) -> None:
    """A plain INSERT of a duplicate address must still be rejected."""
    await conn.execute(
        "INSERT INTO users (email, name) VALUES ('upsert-test3@example.com', 'A')"
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            "INSERT INTO users (email, name) VALUES ('UPSERT-TEST3@example.com', 'B')"
        )
