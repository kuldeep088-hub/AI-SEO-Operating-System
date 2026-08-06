"""Google Search Console API client.

The single most important data source in the product (docs/01 §1): measured
rankings, queries, clicks, impressions and CTR for every site you have access
to, free, for 16 months.

Two behaviours the rest of the system depends on:
  · Data for a given day is not final for ~3 days, so syncs re-pull a rolling
    window and upsert rather than append.
  · Rows are capped at 25,000 per request; anything larger must paginate on
    startRow or it silently truncates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from packages.core.errors import PermanentError, QuotaError, TransientError
from packages.core.logging import get_logger

log = get_logger(__name__)

BASE = "https://www.googleapis.com/webmasters/v3"
ROW_LIMIT = 25_000

# GSC finalises data with a lag. Re-pulling this many days each sync keeps
# late-arriving rows correct instead of permanently under-reporting.
VOLATILE_DAYS = 5


@dataclass(frozen=True, slots=True)
class GscProperty:
    site_url: str
    permission_level: str

    @property
    def is_usable(self) -> bool:
        # siteUnverifiedUser cannot read Search Analytics.
        return self.permission_level != "siteUnverifiedUser"

    @property
    def display(self) -> str:
        return self.site_url.removeprefix("sc-domain:")


def _raise_for(res: httpx.Response, context: str) -> None:
    if res.status_code == 200:
        return
    if res.status_code == 429:
        raise QuotaError(f"Search Console quota exhausted ({context})", retry_after=3600)
    if res.status_code in (401, 403):
        raise PermanentError(
            f"Search Console denied access ({context}). Check the property is shared "
            f"with this Google account and the API is enabled. [{res.status_code}]"
        )
    if res.status_code >= 500:
        raise TransientError(f"Search Console {res.status_code} ({context})")
    raise PermanentError(f"Search Console error {res.status_code} ({context}): {res.text[:200]}")


async def list_properties(access_token: str) -> list[GscProperty]:
    """Every property this Google account can see."""
    async with httpx.AsyncClient(timeout=30) as http:
        res = await http.get(
            f"{BASE}/sites", headers={"Authorization": f"Bearer {access_token}"}
        )
    _raise_for(res, "list sites")
    return [
        GscProperty(site_url=e["siteUrl"], permission_level=e.get("permissionLevel", ""))
        for e in res.json().get("siteEntry", [])
    ]


async def query_search_analytics(
    access_token: str,
    site_url: str,
    start: date,
    end: date,
    *,
    dimensions: tuple[str, ...] = ("date", "query", "page"),
    row_limit: int = ROW_LIMIT,
) -> list[dict[str, Any]]:
    """Paginate Search Analytics fully. Never returns a truncated page."""
    rows: list[dict[str, Any]] = []
    start_row = 0

    async with httpx.AsyncClient(timeout=120) as http:
        while True:
            res = await http.post(
                f"{BASE}/sites/{_quote(site_url)}/searchAnalytics/query",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": list(dimensions),
                    "rowLimit": row_limit,
                    "startRow": start_row,
                    "dataState": "all",
                },
            )
            _raise_for(res, f"query {site_url}")
            page = res.json().get("rows", [])
            rows.extend(page)

            if len(page) < row_limit:
                break
            start_row += row_limit
            if start_row > 1_000_000:  # safety valve; no real site reaches this
                log.warning("gsc.pagination_cap", site_url=site_url, rows=len(rows))
                break

    log.info("gsc.query", site_url=site_url, start=str(start), end=str(end), rows=len(rows))
    return rows


def _quote(site_url: str) -> str:
    """URL-encode a property id for a path segment.

    Domain properties look like `sc-domain:acme.com`; URL-prefix properties look
    like `https://acme.com/`. Both must be fully encoded, colons and slashes
    included, or the path resolves to the wrong endpoint.
    """
    from urllib.parse import quote

    return quote(site_url, safe="")


def to_daily_rows(
    api_rows: list[dict[str, Any]], *, org_id: str, site_id: str
) -> list[tuple[Any, ...]]:
    """Map API rows onto gsc_daily tuples for a COPY/executemany insert."""
    out: list[tuple[Any, ...]] = []
    for r in api_rows:
        keys = r.get("keys", [])
        if len(keys) < 3:
            continue
        day, query, page = keys[0], keys[1], keys[2]
        out.append(
            (
                org_id,
                site_id,
                date.fromisoformat(day),
                query[:1000],
                page[:2000],
                "zzz",
                "ALL",
                int(r.get("clicks", 0)),
                int(r.get("impressions", 0)),
                float(r.get("ctr", 0.0)),
                float(r.get("position", 0.0)),
            )
        )
    return out
