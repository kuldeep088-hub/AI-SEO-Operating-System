"""Google token lifecycle.

The worker needs valid tokens at 02:00 with nobody watching, so refresh is
automatic and a revoked grant is a first-class, isolated outcome: it pauses one
organisation's syncs and surfaces a "Reconnect Google" prompt, never taking down
the app. See docs/06-api-auth.md §16.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import httpx

from packages.core.config import settings
from packages.core.crypto import decrypt, encrypt
from packages.core.errors import PermanentError, TransientError
from packages.core.logging import get_logger

log = get_logger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — a URL

DATA_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


@dataclass(frozen=True, slots=True)
class GoogleTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: list[str]
    account_email: str | None = None


async def store_connection(
    conn: asyncpg.Connection,
    *,
    org_id: str,
    user_id: str,
    tokens: GoogleTokens,
) -> None:
    """Persist tokens encrypted at rest. Never store plaintext."""
    await conn.execute(
        """
        INSERT INTO oauth_connections (
            org_id, user_id, provider, access_token_enc, refresh_token_enc,
            token_expires_at, scopes, account_email
        )
        VALUES ($1, $2, 'google', $3, $4, $5, $6, $7)
        ON CONFLICT (org_id, user_id, provider) DO UPDATE
            SET access_token_enc  = EXCLUDED.access_token_enc,
                refresh_token_enc = EXCLUDED.refresh_token_enc,
                token_expires_at  = EXCLUDED.token_expires_at,
                scopes            = EXCLUDED.scopes,
                account_email     = EXCLUDED.account_email,
                revoked_at        = NULL,
                updated_at        = now()
        """,
        org_id, user_id,
        encrypt(tokens.access_token), encrypt(tokens.refresh_token),
        tokens.expires_at, tokens.scopes, tokens.account_email,
    )


async def get_access_token(conn: asyncpg.Connection, org_id: str) -> str:
    """Return a valid access token, refreshing it if it expires within 5 minutes."""
    row = await conn.fetchrow(
        """
        SELECT id, user_id, access_token_enc, refresh_token_enc, token_expires_at
        FROM   oauth_connections
        WHERE  org_id = $1 AND provider = 'google' AND revoked_at IS NULL
        ORDER  BY updated_at DESC
        LIMIT  1
        """,
        org_id,
    )
    if row is None:
        raise PermanentError(
            "No Google account connected. Connect one in Settings → Integrations."
        )

    if row["token_expires_at"] > datetime.now(UTC) + timedelta(minutes=5):
        return str(decrypt(row["access_token_enc"]))

    refresh_token = decrypt(row["refresh_token_enc"])
    async with httpx.AsyncClient(timeout=20) as http:
        res = await http.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )

    if res.status_code == 400:
        # invalid_grant — the user revoked access, or the refresh token expired.
        # Retrying cannot help; pause this org and tell someone.
        await conn.execute(
            "UPDATE oauth_connections SET revoked_at = now() WHERE id = $1", row["id"]
        )
        log.warning("google.token_revoked", org_id=org_id)
        raise PermanentError(
            "Google access was revoked. Reconnect the account to resume syncing."
        )
    if res.status_code != 200:
        raise TransientError(f"Google token refresh failed ({res.status_code})")

    payload = res.json()
    access: str = payload["access_token"]
    expires_at = datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 3600))

    await conn.execute(
        """
        UPDATE oauth_connections
        SET    access_token_enc = $2, token_expires_at = $3, updated_at = now()
        WHERE  id = $1
        """,
        row["id"], encrypt(access), expires_at,
    )
    log.info("google.token_refreshed", org_id=org_id)
    return access


async def exchange_code(
    code: str, redirect_uri: str
) -> tuple[GoogleTokens, dict[str, Any]]:
    """Swap an authorisation code for tokens, and fetch the account's identity."""
    async with httpx.AsyncClient(timeout=20) as http:
        res = await http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if res.status_code != 200:
            raise PermanentError(f"Token exchange failed: {res.text[:200]}")
        payload = res.json()

        info = await http.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        identity = info.json() if info.status_code == 200 else {}

    return (
        GoogleTokens(
            access_token=payload["access_token"],
            # Google omits refresh_token when re-consenting without prompt=consent.
            refresh_token=payload.get("refresh_token", ""),
            expires_at=datetime.now(UTC) + timedelta(seconds=payload.get("expires_in", 3600)),
            scopes=payload.get("scope", "").split(),
            account_email=identity.get("email"),
        ),
        identity,
    )
