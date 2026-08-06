"""Google OAuth — identity grant only.

The data scopes (Search Console, Analytics) are requested separately, later,
on a screen that explains them. Asking for Search Console access on the sign-in
screen is the biggest drop-off risk in onboarding. See docs/06-api-auth.md §16.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from apps.api.deps import ROLE_PERMISSIONS, SESSION_COOKIE, CurrentPrincipal
from packages.core.config import settings
from packages.core.crypto import hash_token, new_token
from packages.core.logging import get_logger
from packages.core.ratelimit import OAUTH_START_PER_IP, client_ip, enforce
from packages.core.urls import safe_redirect_path
from packages.db.engine import system_tx, tenant_tx

router = APIRouter(prefix="/v1/auth", tags=["auth"])
log = get_logger(__name__)

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"  # noqa: S105 — a URL, not a secret
GOOGLE_USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"

IDENTITY_SCOPES = ["openid", "email", "profile"]

# Requested later, on the onboarding screen that explains each one.
DATA_SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def _slugify(value: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in value]
    return "".join(keep).strip("-")[:40] or "org"


@router.get("/google/start")
async def google_start(request: Request, redirect_to: str = "/") -> RedirectResponse:
    # This endpoint INSERTs into oauth_states before anyone has authenticated,
    # so it is the cheapest way for an anonymous caller to make us write. §27
    # has no limit for it because §27 assumed nothing unauthenticated could
    # reach us at all.
    enforce(request, client_ip(request), OAUTH_START_PER_IP, scope="oauth_start")

    if not settings.google_configured:
        raise HTTPException(
            503,
            detail=(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in .env — see docs/14-execution.md §60."
            ),
        )

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)

    async with system_tx() as conn:
        await conn.execute(
            """
            INSERT INTO oauth_states (state, code_verifier, redirect_to, expires_at)
            VALUES ($1, $2, $3, now() + interval '5 minutes')
            """,
            state, verifier, safe_redirect_path(redirect_to),
        )

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.api_url}/v1/auth/google/callback",
        "response_type": "code",
        "scope": " ".join(IDENTITY_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    qs = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
    return RedirectResponse(f"{GOOGLE_AUTH}?{qs}")


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
) -> RedirectResponse:
    # Google reports a refused authorisation by redirecting HERE with `error`
    # and no `code` — pressing Cancel on the consent screen is the common case,
    # and on a public deployment that happens constantly. `code` used to be a
    # required query parameter, so this path returned FastAPI's raw 422
    # validation JSON in the browser: a dead end with no way back.
    if error or code is None:
        log.info("auth.oauth_refused", error=error or "missing_code")
        # Only when there is a state to clean up. A bare callback hit — a
        # stale bookmark, a crawler — should not cost a database round trip on
        # an unauthenticated path; sweep_expired() collects the rest anyway.
        if state:
            async with system_tx() as conn:
                await conn.execute("DELETE FROM oauth_states WHERE state = $1", state)
        return RedirectResponse(
            f"{settings.web_url}/login?{urlencode({'oauth_error': error or 'missing_code'})}"
        )

    async with system_tx() as conn:
        # Single-use: consume the state as we validate it.
        row = await conn.fetchrow(
            "DELETE FROM oauth_states WHERE state = $1 AND expires_at > now() RETURNING *",
            state,
        )
    if row is None:
        raise HTTPException(400, detail="Invalid or expired OAuth state")

    async with httpx.AsyncClient(timeout=20) as http:
        token_res = await http.post(
            GOOGLE_TOKEN,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.api_url}/v1/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code != 200:
            log.error("auth.token_exchange_failed", status=token_res.status_code)
            raise HTTPException(400, detail="Token exchange with Google failed")
        tokens = token_res.json()

        info_res = await http.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        info_res.raise_for_status()
        info = info_res.json()

    email, sub = info["email"], info["sub"]
    name, picture = info.get("name"), info.get("picture")

    async with system_tx() as conn:
        user = await conn.fetchrow(
            """
            INSERT INTO users (email, name, avatar_url, google_sub, last_seen_at)
            VALUES ($1, $2, $3, $4, now())
            -- Matches the users_email_lower expression index. There is no plain
            -- UNIQUE on email: the bundled Postgres has no citext extension, so
            -- case-insensitive uniqueness is enforced on lower(email) instead.
            -- The doubled parentheses are required for an expression target.
            ON CONFLICT ((lower(email))) DO UPDATE
                SET name = EXCLUDED.name,
                    avatar_url = EXCLUDED.avatar_url,
                    google_sub = EXCLUDED.google_sub,
                    last_seen_at = now()
            RETURNING id
            """,
            email, name, picture, sub,
        )
        user_id = user["id"]

        membership = await conn.fetchrow(
            "SELECT org_id, role FROM memberships WHERE user_id = $1 LIMIT 1", user_id
        )

        # First sign-in creates the organization and makes this user its owner.
        if membership is None:
            org_name = (name or email.split("@")[0]) + "'s Agency"
            base = _slugify(org_name)
            org = await conn.fetchrow(
                "INSERT INTO organizations (name, slug) VALUES ($1, $2) RETURNING id",
                org_name, f"{base}-{secrets.token_hex(3)}",
            )
            await conn.execute(
                "INSERT INTO memberships (org_id, user_id, role) VALUES ($1, $2, 'owner')",
                org["id"], user_id,
            )
            org_id, role = org["id"], "owner"
            log.info("auth.org_created", org_id=str(org_id), email=email)
        else:
            org_id, role = membership["org_id"], membership["role"]

        session_token = new_token()
        await conn.execute(
            """
            INSERT INTO sessions (token_hash, user_id, org_id, ip, user_agent, expires_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            hash_token(session_token),
            user_id,
            org_id,
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
            datetime.now(UTC) + timedelta(days=30),
        )
        await conn.execute(
            """
            INSERT INTO audit_log (org_id, user_id, action, metadata)
            VALUES ($1, $2, 'auth.login', $3::jsonb)
            """,
            org_id, user_id, '{"provider":"google"}',
        )

    log.info("auth.login", email=email, org_id=str(org_id), role=role)

    # Re-validated on the way out, not just on the way in: rows written before
    # safe_redirect_path existed are still in the table, and this is the line
    # that actually leaves the origin.
    response = RedirectResponse(f"{settings.web_url}{safe_redirect_path(row['redirect_to'])}")
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=30 * 24 * 3600,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(
    seoos_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> JSONResponse:
    if seoos_session:
        async with system_tx() as conn:
            await conn.execute(
                "UPDATE sessions SET revoked_at = now() WHERE token_hash = $1",
                hash_token(seoos_session),
            )
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/me")
async def me(principal: CurrentPrincipal) -> dict[str, object]:
    # `organizations` is not a tenant table (it is the tenant), so it stays on
    # system_tx. `oauth_connections` is one, and reading it without an org
    # context returns nothing — this reported data_scopes_granted=false for
    # every org, including ones that had connected Google successfully.
    async with system_tx() as conn:
        org = await conn.fetchrow(
            "SELECT name, slug, brand_color FROM organizations WHERE id = $1",
            principal.org_id,
        )
    async with tenant_tx(principal.org_id, principal.role) as conn:
        has_google_data = await conn.fetchval(
            """
            SELECT EXISTS(
                SELECT 1 FROM oauth_connections
                WHERE org_id = $1 AND provider = 'google' AND revoked_at IS NULL
            )
            """,
            principal.org_id,
        )
    return {
        "user": {
            "id": principal.user_id,
            "email": principal.email,
            "name": principal.name,
        },
        "org": {
            "id": principal.org_id,
            "name": org["name"] if org else None,
            "slug": org["slug"] if org else None,
            "brand_color": org["brand_color"] if org else None,
        },
        "role": principal.role,
        "permissions": sorted(ROLE_PERMISSIONS.get(principal.role, set())),
        "data_scopes_granted": bool(has_google_data),
    }
