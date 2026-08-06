"""Organizations, clients, and sites.

Every handler that touches tenant data runs inside tenant_tx(), which sets the
session variables the RLS policies read. There is no other way to query these
tables. See docs/08-infrastructure.md §28.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.deps import CurrentPrincipal, require, verify_org
from packages.db.engine import tenant_tx

router = APIRouter(prefix="/v1/orgs", tags=["organizations"])


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=100)


class SiteCreate(BaseModel):
    domain: str = Field(min_length=3, max_length=255)
    start_url: str = Field(min_length=8, max_length=500)
    is_primary: bool = True
    gsc_property: str | None = None
    ga4_property_id: str | None = None


def _envelope(rows: list[Any], total: int | None = None) -> dict[str, Any]:
    data = [dict(r) for r in rows]
    return {
        "data": data,
        "meta": {"total": total if total is not None else len(data)},
    }


@router.get("/{org_id}/clients")
async def list_clients(
    org_id: str,
    principal: Annotated[Any, Depends(verify_org)],
) -> dict[str, Any]:
    async with tenant_tx(principal.org_id, principal.role, principal.client_id) as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.name, c.industry, c.created_at,
                   count(s.id) FILTER (WHERE s.deleted_at IS NULL) AS site_count
            FROM   clients c
            LEFT JOIN sites s ON s.client_id = c.id
            WHERE  c.deleted_at IS NULL
            GROUP BY c.id
            ORDER BY c.name
            """
        )
    return _envelope(rows)


@router.post("/{org_id}/clients", status_code=201)
async def create_client(
    org_id: str,
    body: ClientCreate,
    principal: CurrentPrincipal,
    _: Annotated[Any, Depends(require("client:write"))],
) -> dict[str, Any]:
    await verify_org(org_id, principal)
    async with tenant_tx(principal.org_id, principal.role) as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO clients (org_id, name, industry)
            VALUES ($1, $2, $3)
            RETURNING id, name, industry, created_at
            """,
            principal.org_id, body.name, body.industry,
        )
        await conn.execute(
            """
            INSERT INTO audit_log (org_id, user_id, action, entity_type, entity_id)
            VALUES ($1, $2, 'client.create', 'client', $3)
            """,
            principal.org_id, principal.user_id, row["id"],
        )
    return {"data": dict(row)}


@router.get("/{org_id}/clients/{client_id}/sites")
async def list_sites(
    org_id: str,
    client_id: str,
    principal: Annotated[Any, Depends(verify_org)],
) -> dict[str, Any]:
    async with tenant_tx(principal.org_id, principal.role, principal.client_id) as conn:
        rows = await conn.fetch(
            """
            SELECT id, domain, start_url, is_primary,
                   gsc_property, ga4_property_id, created_at
            FROM   sites
            WHERE  client_id = $1 AND deleted_at IS NULL
            ORDER BY is_primary DESC, domain
            """,
            client_id,
        )
    return _envelope(rows)


@router.post("/{org_id}/clients/{client_id}/sites", status_code=201)
async def create_site(
    org_id: str,
    client_id: str,
    body: SiteCreate,
    principal: CurrentPrincipal,
    _: Annotated[Any, Depends(require("site:write"))],
) -> dict[str, Any]:
    await verify_org(org_id, principal)
    async with tenant_tx(principal.org_id, principal.role) as conn:
        # RLS makes this SELECT return nothing for another tenant's client,
        # which turns a cross-tenant write attempt into a clean 404.
        owns = await conn.fetchval(
            "SELECT 1 FROM clients WHERE id = $1 AND deleted_at IS NULL", client_id
        )
        if not owns:
            raise HTTPException(404, detail="Client not found")

        row = await conn.fetchrow(
            """
            INSERT INTO sites (org_id, client_id, domain, start_url, is_primary,
                               gsc_property, ga4_property_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, domain, start_url, is_primary, created_at
            """,
            principal.org_id, client_id, body.domain, body.start_url,
            body.is_primary, body.gsc_property, body.ga4_property_id,
        )
    return {"data": dict(row)}


@router.get("/{org_id}/overview")
async def overview(
    org_id: str,
    principal: Annotated[Any, Depends(verify_org)],
) -> dict[str, Any]:
    """Cross-client dashboard data (docs/04-ui-ux.md §11).

    Reads the materialised view, never live aggregation.
    """
    async with tenant_tx(principal.org_id, principal.role, principal.client_id) as conn:
        rows = await conn.fetch(
            """
            SELECT s.id AS site_id, s.domain, c.id AS client_id, c.name AS client_name,
                   COALESCE(k.clicks_28d, 0)        AS clicks_28d,
                   COALESCE(k.clicks_prev_28d, 0)   AS clicks_prev_28d,
                   COALESCE(k.impressions_28d, 0)   AS impressions_28d,
                   k.avg_position_28d,
                   (SELECT count(*) FROM issues i
                     WHERE i.site_id = s.id AND i.state = 'open'
                       AND i.severity = 'critical')  AS critical_issues
            FROM   sites s
            JOIN   clients c        ON c.id = s.client_id
            LEFT JOIN mv_site_kpis k ON k.site_id = s.id
            WHERE  s.deleted_at IS NULL AND c.deleted_at IS NULL
            ORDER BY critical_issues DESC, clicks_28d DESC
            """
        )
        totals = await conn.fetchrow(
            """
            SELECT count(DISTINCT c.id) AS clients,
                   count(DISTINCT s.id) AS sites
            FROM   clients c LEFT JOIN sites s ON s.client_id = c.id AND s.deleted_at IS NULL
            WHERE  c.deleted_at IS NULL
            """
        )
    return {
        "data": [dict(r) for r in rows],
        "meta": {"clients": totals["clients"], "sites": totals["sites"]},
    }
