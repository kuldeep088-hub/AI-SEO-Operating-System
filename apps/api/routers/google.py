"""Google data connection — incremental scope grant, property discovery, sync.

The data scopes are requested here, separately from sign-in, on a screen that
explains them. Asking for Search Console access on the login screen is the
biggest drop-off risk in onboarding (docs/06-api-auth.md §16).
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from apps.api.deps import CurrentPrincipal, require
from apps.worker.runner import enqueue
from apps.worker.scheduler import ensure_site_schedules
from packages.core.config import settings
from packages.core.logging import get_logger
from packages.core.urls import safe_redirect_path
from packages.db.engine import system_tx, tenant_tx
from packages.integrations.google import ga4, gsc
from packages.integrations.google.oauth import (
    DATA_SCOPES,
    exchange_code,
    get_access_token,
    store_connection,
)

router = APIRouter(prefix="/v1/google", tags=["google"])
log = get_logger(__name__)

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
REDIRECT = f"{settings.api_url}/v1/google/callback"


class ConnectSite(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=3, max_length=255)
    gsc_property: str | None = None
    ga4_property_id: str | None = None


@router.get("/grant")
async def grant(principal: CurrentPrincipal, redirect_to: str = "/connect") -> RedirectResponse:
    """Request Search Console + Analytics scopes on top of the existing sign-in."""
    if not settings.google_configured:
        raise HTTPException(503, detail="Google OAuth is not configured.")

    state = secrets.token_urlsafe(32)
    async with system_tx() as conn:
        await conn.execute(
            """INSERT INTO oauth_states (state, code_verifier, redirect_to, user_id, expires_at)
               VALUES ($1, '', $2, $3, now() + interval '10 minutes')""",
            state, safe_redirect_path(redirect_to, "/connect"), principal.user_id,
        )

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(["openid", "email", "profile", *DATA_SCOPES]),
        "state": state,
        "access_type": "offline",
        # Required to reliably receive a refresh token on re-grant.
        "prompt": "consent",
        # Carry the sign-in grant forward instead of replacing it.
        "include_granted_scopes": "true",
    }
    return RedirectResponse(f"{GOOGLE_AUTH}?{urlencode(params)}")


@router.get("/callback")
async def callback(code: str = Query(...), state: str = Query(...)) -> RedirectResponse:
    async with system_tx() as conn:
        row = await conn.fetchrow(
            "DELETE FROM oauth_states WHERE state = $1 AND expires_at > now() RETURNING *",
            state,
        )
    if row is None:
        raise HTTPException(400, detail="Invalid or expired state")

    tokens, _ = await exchange_code(code, REDIRECT)

    async with system_tx() as conn:
        membership = await conn.fetchrow(
            "SELECT org_id FROM memberships WHERE user_id = $1 LIMIT 1", row["user_id"]
        )
        if membership is None:
            raise HTTPException(400, detail="No organisation for this user")

        # A partial grant is normal: Google lets the user untick one scope.
        granted = set(tokens.scopes)
        missing = [s for s in DATA_SCOPES if s not in granted]

        if not tokens.refresh_token:
            existing = await conn.fetchval(
                """SELECT refresh_token_enc FROM oauth_connections
                   WHERE org_id = $1 AND provider = 'google'""",
                membership["org_id"],
            )
            if not existing:
                raise HTTPException(
                    400,
                    detail="Google did not return a refresh token. Remove this app at "
                           "myaccount.google.com/permissions and try again.",
                )

        await store_connection(
            conn,
            org_id=str(membership["org_id"]),
            user_id=str(row["user_id"]),
            tokens=tokens,
        )

    log.info("google.data_granted", org_id=str(membership["org_id"]),
             missing=missing)

    # Re-validated on the way out — see safe_redirect_path. The partial flag is
    # merged into the existing query rather than concatenated, because
    # "/connect?x=1" + "?partial=1" is not a URL the browser parses as intended.
    target = urlsplit(safe_redirect_path(row["redirect_to"], "/connect"))
    query = target.query
    if missing:
        query = f"{query}&partial=1" if query else "partial=1"
    path = urlunsplit(("", "", target.path, query, target.fragment))
    return RedirectResponse(f"{settings.web_url}{path}")


@router.get("/properties")
async def properties(principal: CurrentPrincipal) -> dict[str, Any]:
    """Every Search Console and GA4 property this Google account can read."""
    async with system_tx() as conn:
        token = await get_access_token(conn, principal.org_id)

    sc = await gsc.list_properties(token)
    an = await ga4.list_properties(token)

    return {
        "data": {
            "search_console": [
                {
                    "site_url": p.site_url,
                    "display": p.display,
                    "permission": p.permission_level,
                    "usable": p.is_usable,
                }
                for p in sorted(sc, key=lambda x: x.display)
            ],
            "analytics": [
                {
                    "property": p.name,
                    "property_id": p.property_id,
                    "display": p.display_name,
                    "account": p.account_name,
                }
                for p in sorted(an, key=lambda x: x.display_name)
            ],
        },
        "meta": {"search_console": len(sc), "analytics": len(an)},
    }


@router.post("/connect", status_code=201)
async def connect(
    body: ConnectSite,
    principal: CurrentPrincipal,
    _: Annotated[Any, Depends(require("site:write"))],
) -> dict[str, Any]:
    """Create a client + site from chosen properties, then start the backfill."""
    if not body.gsc_property and not body.ga4_property_id:
        raise HTTPException(400, detail="Connect at least one property.")

    async with tenant_tx(principal.org_id, principal.role) as conn:
        client_id = await conn.fetchval(
            """INSERT INTO clients (org_id, name) VALUES ($1, $2) RETURNING id""",
            principal.org_id, body.client_name,
        )
        site = await conn.fetchrow(
            """INSERT INTO sites (org_id, client_id, domain, start_url, is_primary,
                                  gsc_property, ga4_property_id)
               VALUES ($1,$2,$3,$4,true,$5,$6)
               ON CONFLICT (org_id, domain) DO UPDATE
                   SET gsc_property    = COALESCE(EXCLUDED.gsc_property, sites.gsc_property),
                       ga4_property_id = COALESCE(EXCLUDED.ga4_property_id, sites.ga4_property_id),
                       updated_at      = now()
               RETURNING id, domain""",
            principal.org_id, client_id, body.domain.lower().strip(),
            f"https://{body.domain.lower().strip()}/",
            body.gsc_property, body.ga4_property_id,
        )

        jobs = []
        if body.gsc_property:
            jid = await enqueue(conn, "gsc_backfill", org_id=principal.org_id,
                                site_id=str(site["id"]), queue="sync", priority=50)
            jobs.append({"kind": "gsc_backfill", "id": str(jid) if jid else None})
        if body.ga4_property_id:
            jid = await enqueue(conn, "ga4_backfill", org_id=principal.org_id,
                                site_id=str(site["id"]), queue="sync", priority=50)
            jobs.append({"kind": "ga4_backfill", "id": str(jid) if jid else None})

        # The backfill above is one-off. This is what keeps the site current
        # every night without anyone pressing a button (docs §24).
        scheduled = await ensure_site_schedules(
            conn,
            org_id=principal.org_id,
            site_id=str(site["id"]),
            gsc=bool(body.gsc_property),
            ga4=bool(body.ga4_property_id),
        )

    log.info("google.connected", org_id=principal.org_id, domain=site["domain"])
    return {
        "data": {
            "site_id": str(site["id"]),
            "domain": site["domain"],
            "jobs": jobs,
            "schedules": scheduled,
        }
    }


@router.post("/sites/{site_id}/sync", status_code=202)
async def sync_now(
    site_id: str,
    principal: CurrentPrincipal,
    _: Annotated[Any, Depends(require("site:crawl"))],
) -> dict[str, Any]:
    """Manual sync. Priority 50 so it jumps ahead of the nightly queue."""
    async with tenant_tx(principal.org_id, principal.role) as conn:
        site = await conn.fetchrow(
            "SELECT gsc_property, ga4_property_id FROM sites WHERE id = $1", site_id
        )
        if site is None:
            raise HTTPException(404, detail="Site not found")

        jobs = []
        if site["gsc_property"]:
            jid = await enqueue(conn, "gsc_sync", org_id=principal.org_id,
                                site_id=site_id, queue="sync", priority=50)
            jobs.append({"kind": "gsc_sync", "id": str(jid) if jid else None,
                         "queued": jid is not None})
        if site["ga4_property_id"]:
            jid = await enqueue(conn, "ga4_sync", org_id=principal.org_id,
                                site_id=site_id, queue="sync", priority=50)
            jobs.append({"kind": "ga4_sync", "id": str(jid) if jid else None,
                         "queued": jid is not None})

    return {"data": {"jobs": jobs}}


@router.get("/sites/{site_id}/status")
async def sync_status(site_id: str, principal: CurrentPrincipal) -> dict[str, Any]:
    async with tenant_tx(principal.org_id, principal.role) as conn:
        state = await conn.fetch(
            """SELECT source, last_synced_date, last_run_at, last_error, rows_ingested
               FROM sync_state WHERE site_id = $1""",
            site_id,
        )
        jobs = await conn.fetch(
            """SELECT kind, status, progress, error, created_at, finished_at
               FROM jobs WHERE site_id = $1
               ORDER BY created_at DESC LIMIT 5""",
            site_id,
        )
    return {
        "data": {
            "sync_state": [dict(r) for r in state],
            "recent_jobs": [dict(r) for r in jobs],
        }
    }
