"""Principal resolution and RBAC.

Enforcement layer 1 of 2. Layer 2 is Postgres RLS (packages/db/engine.py), which
is the backstop if anything here is wrong. See docs/06-api-auth.md §16.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from packages.core.crypto import hash_token
from packages.db.engine import system_tx

SESSION_COOKIE = "seoos_session"

# Capability model. Deliberately coarse — five roles, explicit permissions.
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {
        "org:read", "org:write", "client:read", "client:write",
        "site:read", "site:write", "site:crawl",
        "content:read", "content:write", "settings:read", "settings:write",
        "billing:read", "billing:write", "member:manage",
    },
    "admin": {
        "org:read", "client:read", "client:write",
        "site:read", "site:write", "site:crawl",
        "content:read", "content:write", "settings:read", "settings:write",
        "billing:read", "member:manage",
    },
    "strategist": {
        "org:read", "client:read", "site:read", "site:crawl",
        "content:read", "content:write", "settings:read",
    },
    "writer": {
        "org:read", "client:read", "site:read", "content:read", "content:write",
    },
    "client_viewer": {
        "site:read", "content:read",
    },
}


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    org_id: str
    role: str
    email: str
    name: str | None = None
    client_id: str | None = None  # set only for client_viewer

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, set())


async def current_principal(
    request: Request,
    seoos_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Principal:
    if not seoos_session:
        raise HTTPException(401, detail="Not authenticated")

    async with system_tx() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.user_id, s.org_id, u.email, u.name, m.role
            FROM   sessions s
            JOIN   users u       ON u.id = s.user_id
            JOIN   memberships m ON m.user_id = s.user_id AND m.org_id = s.org_id
            WHERE  s.token_hash = $1
              AND  s.revoked_at IS NULL
              AND  s.expires_at > now()
            """,
            hash_token(seoos_session),
        )
        if row is None:
            raise HTTPException(401, detail="Session expired or invalid")

        # Activity tracking only — this does NOT extend expires_at, so the 30
        # days set at login is an absolute lifetime, not a sliding one. The
        # comment here used to claim a sliding refresh that was never
        # implemented; an absolute expiry is the safer default for a public
        # deployment anyway, so the comment was corrected rather than the code.
        # sweep_expired() in apps/worker/scheduler.py collects the dead rows.
        await conn.execute(
            "UPDATE sessions SET last_used_at = now() WHERE token_hash = $1",
            hash_token(seoos_session),
        )

    principal = Principal(
        user_id=str(row["user_id"]),
        org_id=str(row["org_id"]),
        role=row["role"],
        email=row["email"],
        name=row["name"],
    )
    request.state.principal = principal
    request.state.org_id = principal.org_id
    return principal


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


def require(permission: str) -> Callable[[Principal], Awaitable[Principal]]:
    """Guard an endpoint with a permission.

    Usage:  @router.post("/sites", dependencies=[Depends(require("site:write"))])
    """

    async def _check(principal: CurrentPrincipal) -> Principal:
        if not principal.can(permission):
            raise HTTPException(
                403, detail=f"Role '{principal.role}' cannot perform '{permission}'"
            )
        return principal

    return _check


async def verify_org(org_id: str, principal: CurrentPrincipal) -> Principal:
    """Path org_id must match the session's org.

    Redundant with RLS by design — this produces a clear 403 instead of a
    silently empty result set.
    """
    if org_id != principal.org_id:
        raise HTTPException(403, detail="Organization mismatch")
    return principal
