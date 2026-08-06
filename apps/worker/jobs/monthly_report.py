"""Monthly report generation — docs/12-roadmap.md Phase 1 week 8.

Assemble the numbers in SQL, have the Report Narrator explain them, store both
in `reports`. The exit criterion for the whole of Phase 1 is that this produces
something the account owner would actually send a client.

The handler enters `tenant_tx()` itself. The worker pool connects privileged on
purpose — the queue claims jobs across every org with SKIP LOCKED, which
returns nothing under the app role — so CLAUDE.md makes each handler
responsible for re-establishing tenant scope before touching tenant data.
`reports` and `agent_runs` are both RLS-protected.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, timedelta
from typing import Any

import asyncpg

from packages.ai.agents.report_narrator import narrate_report
from packages.core.logging import get_logger
from packages.db.engine import tenant_tx
from packages.reporting import assemble_report_data

log = get_logger(__name__)

__all__ = ["default_period", "run"]


def default_period(today: date | None = None) -> tuple[date, date]:
    """The previous whole calendar month.

    A report generated on the 3rd should cover last month, not the three days
    of this one. Search Console also lags ~2 days, so a just-ended month is the
    most recent period that is actually complete.
    """
    today = today or date.today()
    first_of_this_month = today.replace(day=1)
    period_end = first_of_this_month - timedelta(days=1)
    return period_end.replace(day=1), period_end


async def run(
    conn: asyncpg.Connection,
    *,
    org_id: str,
    site_id: str,
    period_start: str | None = None,
    period_end: str | None = None,
    progress: Any = None,
) -> dict[str, Any]:
    """Generate one monthly report. `conn` is the privileged worker connection."""
    if period_start and period_end:
        start, end = date.fromisoformat(period_start), date.fromisoformat(period_end)
    else:
        start, end = default_period()

    # Tenant scope from here on — see the module docstring.
    async with tenant_tx(org_id, "owner") as tconn:
        if progress:
            await progress(pct=10, detail="Assembling figures")
        data = await assemble_report_data(
            tconn, site_id=site_id, period_start=start, period_end=end
        )

        if data["days_with_data"] == 0:
            # Refusing beats generating a confident narrative about nothing.
            log.info("report.skipped_no_data", site_id=site_id, period=str(start))
            return {"skipped": "no Search Console data in this period"}

        if progress:
            await progress(pct=35, detail="Writing the narrative")
        narrative = await narrate_report(
            tconn, org_id=org_id, site_id=site_id, data=data
        )

        if progress:
            await progress(pct=85, detail="Saving")

        # Share token is generated here rather than on demand so a report is
        # linkable the moment it exists. docs/06-api-auth.md §16 treats it as
        # the sole secret for portal access, hence token_urlsafe.
        report_id = await tconn.fetchval(
            """INSERT INTO reports (org_id, site_id, kind, period_start, period_end,
                                    data, narrative, share_token, state)
               VALUES ($1, $2, 'monthly', $3, $4, $5::jsonb, $6, $7, 'draft')
               ON CONFLICT (site_id, kind, period_start) DO UPDATE
                   SET data       = EXCLUDED.data,
                       narrative  = EXCLUDED.narrative,
                       period_end = EXCLUDED.period_end,
                       state      = 'draft'
               RETURNING id""",
            org_id, site_id, start, end,
            json.dumps(data, default=str),
            json.dumps(narrative, default=str),
            secrets.token_urlsafe(32),
        )

    log.info(
        "report.generated",
        site_id=site_id,
        report_id=str(report_id),
        period=f"{start}..{end}",
        clicks=data["totals"]["clicks"],
    )
    return {
        "report_id": str(report_id),
        "period": f"{start}..{end}",
        "clicks": data["totals"]["clicks"],
        "sections": len(narrative.get("sections", [])),
    }
