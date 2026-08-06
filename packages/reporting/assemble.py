"""Assemble every figure a monthly report needs — in SQL.

CLAUDE.md rule 6: never let the model compute a number. Everything the Report
Narrator will mention is aggregated here, by Postgres, and handed over already
calculated — including the percentage changes, which are the figures a language
model is most likely to get subtly wrong while sounding certain.

The period is compared against the immediately preceding window of equal
length, so "vs last month" means the same number of days rather than a calendar
month that might be 28 or 31.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg

from packages.core.logging import get_logger

log = get_logger(__name__)

__all__ = ["assemble_report_data"]


def _pct_change(now: float | None, prev: float | None) -> float | None:
    """None when there is no prior period to compare against.

    Returning 0.0 would be a lie — "no change" and "nothing to compare" are
    different statements, and the narrative should be able to tell them apart.
    """
    if not prev:
        return None
    return round(((float(now or 0) - float(prev)) / float(prev)) * 100, 1)


def _f(value: Any, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


async def assemble_report_data(
    conn: asyncpg.Connection,
    *,
    site_id: str,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Every number the report will contain. `conn` must be tenant-scoped."""
    span = (period_end - period_start).days + 1
    prev_end = period_start
    prev_start = period_start.fromordinal(period_start.toordinal() - span)

    site = await conn.fetchrow(
        """SELECT s.id, s.domain, s.gsc_property, s.ga4_property_id, c.name AS client_name
           FROM   sites s JOIN clients c ON c.id = s.client_id
           WHERE  s.id = $1 AND s.deleted_at IS NULL""",
        site_id,
    )
    if site is None:
        raise ValueError(f"site {site_id} not found in this organisation")

    totals = await conn.fetchrow(
        """SELECT
             sum(clicks)      FILTER (WHERE date BETWEEN $2 AND $3) AS clicks,
             sum(impressions) FILTER (WHERE date BETWEEN $2 AND $3) AS impressions,
             avg(position)    FILTER (WHERE date BETWEEN $2 AND $3) AS position,
             sum(clicks)      FILTER (WHERE date >= $4 AND date < $5) AS prev_clicks,
             sum(impressions) FILTER (WHERE date >= $4 AND date < $5) AS prev_impressions,
             avg(position)    FILTER (WHERE date >= $4 AND date < $5) AS prev_position,
             count(DISTINCT date) FILTER (WHERE date BETWEEN $2 AND $3) AS days
           FROM gsc_daily WHERE site_id = $1""",
        site_id, period_start, period_end, prev_start, prev_end,
    )

    clicks = int(totals["clicks"] or 0)
    impressions = int(totals["impressions"] or 0)
    prev_clicks = int(totals["prev_clicks"] or 0)
    prev_impressions = int(totals["prev_impressions"] or 0)
    position = _f(totals["position"])
    prev_position = _f(totals["prev_position"])

    top_queries = await conn.fetch(
        """SELECT query, sum(clicks) AS clicks, sum(impressions) AS impressions,
                  round((sum(clicks)::numeric / nullif(sum(impressions),0) * 100), 1) AS ctr_pct,
                  round(avg(position)::numeric, 1) AS position
           FROM   gsc_daily
           WHERE  site_id = $1 AND date BETWEEN $2 AND $3 AND query IS NOT NULL
           GROUP  BY query ORDER BY clicks DESC, impressions DESC LIMIT 15""",
        site_id, period_start, period_end,
    )

    top_pages = await conn.fetch(
        """SELECT page, sum(clicks) AS clicks, sum(impressions) AS impressions
           FROM   gsc_daily
           WHERE  site_id = $1 AND date BETWEEN $2 AND $3 AND page IS NOT NULL
           GROUP  BY page ORDER BY clicks DESC LIMIT 10""",
        site_id, period_start, period_end,
    )

    # Movers: this period against the previous one, per query. The delta is
    # computed here so the narrative never has to subtract anything.
    movers = await conn.fetch(
        """WITH cur AS (
             SELECT query, sum(clicks) AS clicks, avg(position) AS position
             FROM gsc_daily
             WHERE site_id = $1 AND date BETWEEN $2 AND $3 AND query IS NOT NULL
             GROUP BY query
           ), prev AS (
             SELECT query, sum(clicks) AS clicks
             FROM gsc_daily
             WHERE site_id = $1 AND date >= $4 AND date < $5 AND query IS NOT NULL
             GROUP BY query
           )
           SELECT coalesce(cur.query, prev.query) AS query,
                  coalesce(cur.clicks, 0)  AS clicks,
                  coalesce(prev.clicks, 0) AS prev_clicks,
                  coalesce(cur.clicks, 0) - coalesce(prev.clicks, 0) AS change,
                  round(cur.position::numeric, 1) AS position
           FROM cur FULL OUTER JOIN prev ON prev.query = cur.query
           WHERE coalesce(cur.clicks, 0) <> coalesce(prev.clicks, 0)
           ORDER BY change DESC""",
        site_id, period_start, period_end, prev_start, prev_end,
    )
    risers = [dict(r) for r in movers if int(r["change"]) > 0][:10]
    fallers = [dict(r) for r in reversed(movers) if int(r["change"]) < 0][:10]

    opportunities = await conn.fetch(
        """SELECT query, impressions, clicks,
                  round(avg_position::numeric, 1) AS position
           FROM   mv_query_opportunities
           WHERE  site_id = $1 ORDER BY impressions DESC LIMIT 10""",
        site_id,
    )

    analytics: dict[str, Any] | None = None
    if site["ga4_property_id"]:
        ga = await conn.fetchrow(
            """SELECT
                 sum(sessions)         FILTER (WHERE date BETWEEN $2 AND $3) AS sessions,
                 sum(engaged_sessions) FILTER (WHERE date BETWEEN $2 AND $3) AS engaged,
                 sum(conversions)      FILTER (WHERE date BETWEEN $2 AND $3) AS conversions,
                 sum(revenue)          FILTER (WHERE date BETWEEN $2 AND $3) AS revenue,
                 sum(sessions)         FILTER (WHERE date >= $4 AND date < $5) AS prev_sessions
               FROM ga4_daily WHERE site_id = $1""",
            site_id, period_start, period_end, prev_start, prev_end,
        )
        if ga and ga["sessions"] is not None:
            analytics = {
                "sessions": int(ga["sessions"] or 0),
                "sessions_previous_period": int(ga["prev_sessions"] or 0),
                "sessions_change_pct": _pct_change(ga["sessions"], ga["prev_sessions"]),
                "engaged_sessions": int(ga["engaged"] or 0),
                "conversions": int(ga["conversions"] or 0),
                "revenue": _f(ga["revenue"], 2),
            }

    data: dict[str, Any] = {
        "site": {
            "domain": site["domain"],
            "client_name": site["client_name"],
            "gsc_property": site["gsc_property"],
        },
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "days_with_data": int(totals["days"] or 0),
        "days_in_period": span,
        "totals": {
            "clicks": clicks,
            "prev_clicks": prev_clicks,
            "clicks_change_pct": _pct_change(clicks, prev_clicks),
            "impressions": impressions,
            "prev_impressions": prev_impressions,
            "impressions_change_pct": _pct_change(impressions, prev_impressions),
            "ctr_pct": round(clicks / impressions * 100, 2) if impressions else None,
            "avg_position": position,
            "prev_avg_position": prev_position,
            # Negative means the average position number fell, which is an
            # improvement. Named in the payload so nothing downstream has to
            # remember the convention.
            "position_change": (
                None if position is None or prev_position is None
                else round(position - prev_position, 1)
            ),
        },
        "analytics": analytics,
        "top_queries": [dict(r) for r in top_queries],
        "top_pages": [dict(r) for r in top_pages],
        "risers": risers,
        "fallers": fallers,
        "opportunities": [dict(r) for r in opportunities],
    }

    log.info(
        "report.assembled",
        site_id=site_id,
        days_with_data=data["days_with_data"],
        clicks=clicks,
        queries=len(data["top_queries"]),
    )
    return data
