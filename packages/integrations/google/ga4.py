"""Google Analytics 4 — Admin API for discovery, Data API for reporting.

GA4 is what turns "we rank #4" into "we rank #4 and it produced 22 conversions"
(docs/01 §2, problem 2). The join happens on landing page, which is why the
report always requests `landingPage` even when it costs an extra dimension.

Quota is token-based rather than request-based, so the sync asks for wide date
ranges in few calls rather than many small ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from packages.core.errors import PermanentError, QuotaError, TransientError
from packages.core.logging import get_logger

log = get_logger(__name__)

ADMIN = "https://analyticsadmin.googleapis.com/v1beta"
DATA = "https://analyticsdata.googleapis.com/v1beta"


@dataclass(frozen=True, slots=True)
class Ga4Property:
    name: str          # "properties/123456789"
    display_name: str
    account_name: str

    @property
    def property_id(self) -> str:
        return self.name.split("/")[-1]


def _raise_for(res: httpx.Response, context: str) -> None:
    if res.status_code == 200:
        return
    if res.status_code == 429:
        raise QuotaError(f"GA4 quota exhausted ({context})", retry_after=3600)
    if res.status_code in (401, 403):
        raise PermanentError(
            f"GA4 denied access ({context}). Check the property is shared with this "
            f"Google account and the Analytics Data API is enabled. [{res.status_code}]"
        )
    if res.status_code >= 500:
        raise TransientError(f"GA4 {res.status_code} ({context})")
    raise PermanentError(f"GA4 error {res.status_code} ({context}): {res.text[:200]}")


async def list_properties(access_token: str) -> list[Ga4Property]:
    """Every GA4 property this account can read, across all accounts."""
    props: list[Ga4Property] = []
    async with httpx.AsyncClient(timeout=30) as http:
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"pageSize": 200}
            if page_token:
                params["pageToken"] = page_token
            res = await http.get(
                f"{ADMIN}/accountSummaries",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
            _raise_for(res, "list properties")
            body = res.json()
            for account in body.get("accountSummaries", []):
                account_name = account.get("displayName", "")
                for p in account.get("propertySummaries", []):
                    props.append(
                        Ga4Property(
                            name=p["property"],
                            display_name=p.get("displayName", p["property"]),
                            account_name=account_name,
                        )
                    )
            page_token = body.get("nextPageToken")
            if not page_token:
                break
    return props


async def run_report(
    access_token: str,
    property_id: str,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Sessions, conversions and revenue by date, landing page and channel."""
    rows: list[dict[str, Any]] = []
    offset = 0
    limit = 100_000

    async with httpx.AsyncClient(timeout=120) as http:
        while True:
            res = await http.post(
                f"{DATA}/properties/{property_id}:runReport",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "dateRanges": [
                        {"startDate": start.isoformat(), "endDate": end.isoformat()}
                    ],
                    "dimensions": [
                        {"name": "date"},
                        {"name": "landingPagePlusQueryString"},
                        {"name": "sessionDefaultChannelGroup"},
                    ],
                    "metrics": [
                        {"name": "sessions"},
                        {"name": "engagedSessions"},
                        {"name": "conversions"},
                        {"name": "totalRevenue"},
                    ],
                    "limit": limit,
                    "offset": offset,
                    "keepEmptyRows": False,
                },
            )
            _raise_for(res, f"report {property_id}")
            body = res.json()
            page = body.get("rows", [])
            rows.extend(page)

            total = int(body.get("rowCount", 0))
            offset += len(page)
            if not page or offset >= total:
                break

    log.info("ga4.report", property_id=property_id, start=str(start),
             end=str(end), rows=len(rows))
    return rows


def to_daily_rows(
    api_rows: list[dict[str, Any]], *, org_id: str, site_id: str
) -> list[tuple[Any, ...]]:
    """Map runReport rows onto ga4_daily tuples."""
    out: list[tuple[Any, ...]] = []
    for r in api_rows:
        dims = [d.get("value", "") for d in r.get("dimensionValues", [])]
        mets = [m.get("value", "0") for m in r.get("metricValues", [])]
        if len(dims) < 3 or len(mets) < 4:
            continue
        raw_date, landing_page, channel = dims[0], dims[1], dims[2]
        try:
            # GA4 returns YYYYMMDD
            day = date(int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8]))
        except (ValueError, IndexError):
            continue
        out.append(
            (
                org_id,
                site_id,
                day,
                landing_page[:2000],
                channel[:100] or "unassigned",
                int(float(mets[0] or 0)),
                int(float(mets[1] or 0)),
                float(mets[2] or 0),
                float(mets[3] or 0),
            )
        )
    return out
