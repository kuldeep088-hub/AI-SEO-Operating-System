"""The GSC⋈GA4 join — docs/12-roadmap.md Phase 1 week 3.

Search Console and Analytics both describe pages, and neither agrees on how to
spell one:

    gsc_daily.page          https://acme.com/services
    ga4_daily.landing_page  /services

So the two datasets have sat side by side, never joined, and the question the
join exists to answer — *did the traffic this page earns actually do anything?*
— could not be asked.

**Why a view rather than a helper in each codebase.** The normalisation is
fiddly (scheme, host, trailing slash, query string, fragment) and both the
Python reporting layer and the TypeScript web app need it. Two copies would
drift, and CLAUDE.md rule 8 forbids duplicating domain logic. Postgres is the
one place both already share.

**`security_invoker = true` is load-bearing.** By default a Postgres view
evaluates the underlying tables' RLS policies against the *view owner*, not the
caller. This view is created by the migration role, which owns the tenant
tables — so without this setting the view would read every organisation's rows
regardless of who queried it, and it would look completely normal doing it.
That is the same shape as the cross-tenant leak this project already had once.
`tests/isolation/test_page_performance_view.py` checks it rather than trusting
it.

Revision ID: 0004
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IMMUTABLE so the planner can use it in an index expression later, and so
    # it is inlined rather than called per row.
    op.execute(
        """
        CREATE FUNCTION seo_page_path(url text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
            SELECT CASE
                WHEN url IS NULL THEN NULL
                ELSE coalesce(
                    nullif(
                        -- strip scheme+host, then query, then fragment, then a
                        -- trailing slash; '/services/' and '/services' are the
                        -- same page and GSC and GA4 disagree about which.
                        regexp_replace(
                            regexp_replace(
                                regexp_replace(
                                    regexp_replace(url, '^https?://[^/]*', ''),
                                    '\\?.*$', ''),
                                '#.*$', ''),
                            '(.)/$', '\\1'),
                        ''),
                    '/')
            END
        $$
        """
    )

    op.execute(
        """
        CREATE VIEW page_performance WITH (security_invoker = true) AS
        WITH search AS (
            SELECT org_id, site_id, date,
                   seo_page_path(page) AS path,
                   sum(clicks)      AS clicks,
                   sum(impressions) AS impressions,
                   avg(position)    AS position
            FROM   gsc_daily
            WHERE  page IS NOT NULL
            GROUP  BY org_id, site_id, date, seo_page_path(page)
        ), behaviour AS (
            SELECT org_id, site_id, date,
                   seo_page_path(landing_page) AS path,
                   sum(sessions)         AS sessions,
                   sum(engaged_sessions) AS engaged_sessions,
                   sum(conversions)      AS conversions,
                   sum(revenue)          AS revenue
            FROM   ga4_daily
            WHERE  landing_page IS NOT NULL
            GROUP  BY org_id, site_id, date, seo_page_path(landing_page)
        )
        -- FULL OUTER: a page can earn impressions and no sessions (nobody
        -- clicked) or sessions and no impressions (arrived from elsewhere).
        -- Both are findings; an inner join would hide them.
        SELECT
            coalesce(s.org_id,  b.org_id)  AS org_id,
            coalesce(s.site_id, b.site_id) AS site_id,
            coalesce(s.date,    b.date)    AS date,
            coalesce(s.path,    b.path)    AS path,
            coalesce(s.clicks, 0)          AS clicks,
            coalesce(s.impressions, 0)     AS impressions,
            s.position                     AS position,
            coalesce(b.sessions, 0)        AS sessions,
            coalesce(b.engaged_sessions, 0) AS engaged_sessions,
            coalesce(b.conversions, 0)     AS conversions,
            coalesce(b.revenue, 0)         AS revenue,
            (s.site_id IS NOT NULL)        AS in_search_console,
            (b.site_id IS NOT NULL)        AS in_analytics
        FROM search s
        FULL OUTER JOIN behaviour b
          ON  b.site_id = s.site_id
          AND b.date    = s.date
          AND b.path    = s.path
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS page_performance")
    op.execute("DROP FUNCTION IF EXISTS seo_page_path(text)")
