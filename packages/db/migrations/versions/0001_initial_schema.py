"""Initial schema — the complete design from docs/05-database.md §13.

Written as raw SQL rather than SQLAlchemy models because this schema uses
partitioning, RLS, generated columns, pgvector, and partial unique indexes —
all of which are clearer and more reliable expressed directly.

Revision ID: 0001
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ───────────────────────────────────────────────────────────
    # `vector` is required. The rest are optimisations that the Docker image
    # ships but the bundled pgserver build does not, so they are optional:
    # gen_random_uuid() and sha256() are core in Postgres 13+/11+ respectively,
    # so nothing below depends on pgcrypto. See scripts/pg.py.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("""
        DO $$
        DECLARE ext text;
        BEGIN
            FOREACH ext IN ARRAY ARRAY['pg_trgm','btree_gin','citext','pgcrypto'] LOOP
                BEGIN
                    EXECUTE format('CREATE EXTENSION IF NOT EXISTS %I', ext);
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'optional extension % unavailable — skipping', ext;
                END;
            END LOOP;
        END
        $$;
    """)

    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TYPE user_role      AS ENUM ('owner','admin','strategist','writer','client_viewer');
        CREATE TYPE job_status     AS ENUM ('queued','running','succeeded','failed','dead');
        CREATE TYPE issue_severity AS ENUM ('critical','warning','notice');
        CREATE TYPE issue_state    AS ENUM ('open','resolved','ignored');
        CREATE TYPE content_state  AS ENUM ('idea','brief','drafting','review','approved','published');
        CREATE TYPE search_intent  AS ENUM ('informational','commercial','transactional','navigational');
        CREATE TYPE provider_kind  AS ENUM ('local','remote');
    """)

    # ── Tenancy ──────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE organizations (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            name        text NOT NULL,
            slug        text NOT NULL UNIQUE,
            logo_path   text,
            brand_color text DEFAULT '#1a4d2e',
            settings    jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            deleted_at  timestamptz
        );

        CREATE TABLE users (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email        text NOT NULL,
            name         text,
            avatar_url   text,
            google_sub   text UNIQUE,
            last_seen_at timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now(),
            deleted_at   timestamptz
        );
        -- Case-insensitive uniqueness without the citext extension.
        CREATE UNIQUE INDEX users_email_lower ON users (lower(email));

        CREATE TABLE memberships (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role         user_role NOT NULL DEFAULT 'strategist',
            client_scope uuid[],
            created_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (org_id, user_id)
        );
        CREATE INDEX ON memberships (user_id);

        CREATE TABLE clients (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name        text NOT NULL,
            industry    text,
            brand_voice jsonb NOT NULL DEFAULT '{}'::jsonb,
            settings    jsonb NOT NULL DEFAULT '{}'::jsonb,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            deleted_at  timestamptz
        );
        CREATE INDEX ON clients (org_id) WHERE deleted_at IS NULL;

        CREATE TABLE sites (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            client_id       uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            domain          text NOT NULL,
            start_url       text NOT NULL,
            is_primary      boolean NOT NULL DEFAULT false,
            gsc_property    text,
            ga4_property_id text,
            gbp_location_id text,
            -- Spaces after the colons are load-bearing. SQLAlchemy's text()
            -- treats a colon followed immediately by word characters as a bind
            -- parameter -- including inside SQL comments like this one.
            crawl_config    jsonb NOT NULL DEFAULT
                '{"max_pages": 5000, "max_depth": 10, "delay_ms": 250,
                  "respect_robots": true, "include": [],
                  "exclude": ["/wp-admin/", "/cart/", "?"]}'::jsonb,
            created_at      timestamptz NOT NULL DEFAULT now(),
            updated_at      timestamptz NOT NULL DEFAULT now(),
            deleted_at      timestamptz,
            UNIQUE (org_id, domain)
        );
        CREATE INDEX ON sites (org_id, client_id) WHERE deleted_at IS NULL;

        CREATE TABLE portal_tokens (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            client_id      uuid NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            token_hash     text NOT NULL UNIQUE,
            passcode_hash  text,
            sections       jsonb NOT NULL DEFAULT '["overview","reports","content"]'::jsonb,
            expires_at     timestamptz,
            last_viewed_at timestamptz,
            view_count     integer NOT NULL DEFAULT 0,
            revoked_at     timestamptz,
            created_at     timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE sessions (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            token_hash   text NOT NULL UNIQUE,
            user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            ip           inet,
            user_agent   text,
            expires_at   timestamptz NOT NULL,
            last_used_at timestamptz NOT NULL DEFAULT now(),
            revoked_at   timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ON sessions (user_id) WHERE revoked_at IS NULL;

        CREATE TABLE oauth_states (
            state         text PRIMARY KEY,
            code_verifier text NOT NULL,
            redirect_to   text,
            user_id       uuid REFERENCES users(id) ON DELETE CASCADE,
            expires_at    timestamptz NOT NULL,
            created_at    timestamptz NOT NULL DEFAULT now()
        );
    """)

    # ── Integrations ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE oauth_connections (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id            uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id           uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider          text NOT NULL,
            access_token_enc  bytea NOT NULL,
            refresh_token_enc bytea NOT NULL,
            token_expires_at  timestamptz NOT NULL,
            scopes            text[] NOT NULL,
            account_email     text,
            revoked_at        timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now(),
            updated_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (org_id, user_id, provider)
        );

        CREATE TABLE sync_state (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_id          uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            source           text NOT NULL,
            last_synced_date date,
            last_run_at      timestamptz,
            last_error       text,
            rows_ingested    bigint NOT NULL DEFAULT 0,
            UNIQUE (site_id, source)
        );
    """)

    # ── Metrics (partitioned time series) ────────────────────────────────────
    op.execute("""
        CREATE TABLE gsc_daily (
            org_id      uuid NOT NULL,
            site_id     uuid NOT NULL,
            date        date NOT NULL,
            query       text NOT NULL,
            page        text NOT NULL,
            country     char(3) NOT NULL DEFAULT 'zzz',
            device      text NOT NULL DEFAULT 'ALL',
            clicks      integer NOT NULL DEFAULT 0,
            impressions integer NOT NULL DEFAULT 0,
            ctr         real NOT NULL DEFAULT 0,
            position    real NOT NULL DEFAULT 0,
            PRIMARY KEY (site_id, date, query, page, country, device)
        ) PARTITION BY RANGE (date);

        CREATE INDEX ON gsc_daily (site_id, date DESC);
        CREATE INDEX ON gsc_daily (site_id, query text_pattern_ops);
        CREATE INDEX ON gsc_daily (site_id, page text_pattern_ops);

        CREATE TABLE ga4_daily (
            org_id           uuid NOT NULL,
            site_id          uuid NOT NULL,
            date             date NOT NULL,
            landing_page     text NOT NULL,
            channel          text NOT NULL DEFAULT 'organic',
            sessions         integer NOT NULL DEFAULT 0,
            engaged_sessions integer NOT NULL DEFAULT 0,
            conversions      numeric(12,2) NOT NULL DEFAULT 0,
            revenue          numeric(14,2) NOT NULL DEFAULT 0,
            PRIMARY KEY (site_id, date, landing_page, channel)
        ) PARTITION BY RANGE (date);

        CREATE INDEX ON ga4_daily (site_id, date DESC);
        CREATE INDEX ON ga4_daily (site_id, landing_page text_pattern_ops);

        CREATE TABLE lighthouse_runs (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id         uuid NOT NULL,
            site_id        uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            url            text NOT NULL,
            strategy       text NOT NULL DEFAULT 'mobile',
            performance    smallint, accessibility smallint,
            best_practices smallint, seo smallint,
            lcp_ms integer, cls numeric(5,3), inp_ms integer, ttfb_ms integer,
            raw_path       text,
            run_at         timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ON lighthouse_runs (site_id, url, run_at DESC);

        CREATE TABLE rank_history (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id        uuid NOT NULL,
            site_id       uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            query         text NOT NULL,
            date          date NOT NULL,
            position      real,
            url           text,
            serp_features text[],
            source        text NOT NULL DEFAULT 'local_scraper',
            UNIQUE (site_id, query, date)
        );
    """)

    # Partitions must cover the full GSC backfill window, not just recent months:
    # Search Console serves 16 months of history (§38), and the backfill writes
    # all of it on day one. 18 months back plus 3 forward, with a scheduled job
    # extending the leading edge (§24).
    op.execute("""
        DO $$
        DECLARE
            m date := date_trunc('month', current_date) - interval '18 months';
            i int;
        BEGIN
            FOR i IN 0..21 LOOP
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS gsc_daily_%s PARTITION OF gsc_daily
                     FOR VALUES FROM (%L) TO (%L)',
                    to_char(m, 'YYYY_MM'), m, m + interval '1 month');
                EXECUTE format(
                    'CREATE TABLE IF NOT EXISTS ga4_daily_%s PARTITION OF ga4_daily
                     FOR VALUES FROM (%L) TO (%L)',
                    to_char(m, 'YYYY_MM'), m, m + interval '1 month');
                m := m + interval '1 month';
            END LOOP;
        END
        $$;
    """)

    # ── Crawl and SEO objects ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE crawls (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id        uuid NOT NULL,
            site_id       uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            started_at    timestamptz NOT NULL DEFAULT now(),
            finished_at   timestamptz,
            pages_crawled integer NOT NULL DEFAULT 0,
            pages_failed  integer NOT NULL DEFAULT 0,
            status        job_status NOT NULL DEFAULT 'running',
            error         text
        );

        CREATE TABLE pages (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id            uuid NOT NULL,
            site_id           uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            url               text NOT NULL,
            url_hash          text GENERATED ALWAYS AS (encode(sha256(url::bytea),'hex')) STORED,
            status_code       smallint,
            redirect_to       text,
            content_type      text,
            title             text,
            meta_description  text,
            h1                text,
            canonical         text,
            meta_robots       text,
            lang              text,
            word_count        integer,
            body_text         text,
            schema_types      text[],
            depth             smallint,
            inlinks_count     integer NOT NULL DEFAULT 0,
            outlinks_count    integer NOT NULL DEFAULT 0,
            internal_pagerank real,
            first_seen_at     timestamptz NOT NULL DEFAULT now(),
            last_crawled_at   timestamptz NOT NULL DEFAULT now(),
            last_crawl_id     uuid REFERENCES crawls(id),
            is_gone           boolean NOT NULL DEFAULT false,
            UNIQUE (site_id, url_hash)
        );
        CREATE INDEX ON pages (site_id) WHERE is_gone = false;
        CREATE INDEX ON pages (site_id, status_code);
        CREATE INDEX pages_fts ON pages USING gin (to_tsvector('english', coalesce(body_text,'')));

        CREATE TABLE internal_links (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL,
            site_id      uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            from_page_id uuid NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
            to_page_id   uuid REFERENCES pages(id) ON DELETE CASCADE,
            to_url       text NOT NULL,
            anchor_text  text,
            is_nofollow  boolean NOT NULL DEFAULT false,
            UNIQUE (from_page_id, to_url, anchor_text)
        );
        CREATE INDEX ON internal_links (to_page_id);

        CREATE TABLE issues (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id         uuid NOT NULL,
            site_id        uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            rule_key       text NOT NULL,
            severity       issue_severity NOT NULL,
            state          issue_state NOT NULL DEFAULT 'open',
            affected_count integer NOT NULL DEFAULT 0,
            affected_urls  jsonb NOT NULL DEFAULT '[]'::jsonb,
            explanation    text,
            remediation    text,
            first_seen_at  timestamptz NOT NULL DEFAULT now(),
            last_seen_at   timestamptz NOT NULL DEFAULT now(),
            resolved_at    timestamptz,
            UNIQUE (site_id, rule_key)
        );
        CREATE INDEX ON issues (site_id, state, severity);
        CREATE INDEX ON issues (site_id, first_seen_at DESC) WHERE state = 'open';

        CREATE TABLE keyword_clusters (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id             uuid NOT NULL,
            site_id            uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            label              text NOT NULL,
            intent             search_intent,
            query_count        integer NOT NULL DEFAULT 0,
            total_impressions  bigint NOT NULL DEFAULT 0,
            avg_position       real,
            avg_ctr            real,
            opportunity_score  smallint,
            covered_by_page_id uuid REFERENCES pages(id),
            centroid           vector(768),
            computed_at        timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE cluster_queries (
            cluster_id    uuid NOT NULL REFERENCES keyword_clusters(id) ON DELETE CASCADE,
            query         text NOT NULL,
            impressions   bigint NOT NULL DEFAULT 0,
            avg_position  real,
            search_volume integer,
            PRIMARY KEY (cluster_id, query)
        );

        CREATE TABLE competitors (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id          uuid NOT NULL,
            site_id         uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            domain          text NOT NULL,
            last_crawled_at timestamptz,
            pages_crawled   integer NOT NULL DEFAULT 0,
            analysis        jsonb NOT NULL DEFAULT '{}'::jsonb,
            UNIQUE (site_id, domain)
        );

        CREATE TABLE backlinks (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id        uuid NOT NULL,
            site_id       uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            source_domain text NOT NULL,
            target_url    text NOT NULL,
            link_count    integer NOT NULL DEFAULT 1,
            source        text NOT NULL DEFAULT 'gsc',
            first_seen_at timestamptz NOT NULL DEFAULT now(),
            last_seen_at  timestamptz NOT NULL DEFAULT now(),
            lost_at       timestamptz,
            UNIQUE (site_id, source_domain, target_url)
        );
    """)

    # ── Content ──────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE briefs (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id              uuid NOT NULL,
            site_id             uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            cluster_id          uuid REFERENCES keyword_clusters(id),
            title               text NOT NULL,
            target_queries      jsonb NOT NULL DEFAULT '[]'::jsonb,
            outline             jsonb NOT NULL DEFAULT '[]'::jsonb,
            entities            jsonb NOT NULL DEFAULT '[]'::jsonb,
            internal_links      jsonb NOT NULL DEFAULT '[]'::jsonb,
            competitor_research jsonb NOT NULL DEFAULT '{}'::jsonb,
            word_target_min     integer DEFAULT 1500,
            word_target_max     integer DEFAULT 2500,
            state               content_state NOT NULL DEFAULT 'brief',
            assigned_to         uuid REFERENCES users(id),
            due_date            date,
            approved_by         uuid REFERENCES users(id),
            approved_at         timestamptz,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE drafts (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           uuid NOT NULL,
            brief_id         uuid NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
            version          integer NOT NULL DEFAULT 1,
            title            text,
            meta_description text,
            body_markdown    text,
            schema_jsonld    jsonb,
            coverage         jsonb NOT NULL DEFAULT '{}'::jsonb,
            generated_by     provider_kind NOT NULL DEFAULT 'local',
            created_at       timestamptz NOT NULL DEFAULT now(),
            UNIQUE (brief_id, version)
        );

        CREATE TABLE publications (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL,
            site_id      uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            draft_id     uuid REFERENCES drafts(id),
            url          text NOT NULL,
            published_at timestamptz NOT NULL DEFAULT now(),
            external_id  text,
            UNIQUE (site_id, url)
        );
    """)

    # ── AI ───────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE prompt_versions (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            key           text NOT NULL,
            version       integer NOT NULL,
            body          text NOT NULL,
            output_schema jsonb,
            model_hint    text,
            is_active     boolean NOT NULL DEFAULT false,
            notes         text,
            created_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (key, version)
        );
        CREATE UNIQUE INDEX ON prompt_versions (key) WHERE is_active;

        CREATE TABLE agent_runs (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id            uuid NOT NULL,
            site_id           uuid REFERENCES sites(id) ON DELETE CASCADE,
            agent             text NOT NULL,
            trigger           text NOT NULL,
            prompt_version_id uuid REFERENCES prompt_versions(id),
            provider          provider_kind NOT NULL DEFAULT 'local',
            model             text NOT NULL,
            input             jsonb,
            output            jsonb,
            status            job_status NOT NULL DEFAULT 'running',
            error             text,
            prompt_tokens     integer,
            completion_tokens integer,
            duration_ms       integer,
            started_at        timestamptz NOT NULL DEFAULT now(),
            finished_at       timestamptz
        );
        CREATE INDEX ON agent_runs (org_id, agent, started_at DESC);

        CREATE TABLE agent_steps (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            run_id      uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
            step_index  smallint NOT NULL,
            node        text NOT NULL,
            tool_name   text,
            input       jsonb,
            output      jsonb,
            duration_ms integer,
            created_at  timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE embeddings (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL,
            site_id      uuid REFERENCES sites(id) ON DELETE CASCADE,
            source_type  text NOT NULL,
            source_id    uuid,
            chunk_index  smallint NOT NULL DEFAULT 0,
            content      text NOT NULL,
            embedding    vector(768) NOT NULL,
            metadata     jsonb NOT NULL DEFAULT '{}'::jsonb,
            content_hash text NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (source_type, source_id, chunk_index)
        );
        CREATE INDEX embeddings_hnsw ON embeddings
            USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
        CREATE INDEX ON embeddings (org_id, site_id, source_type);

        CREATE TABLE memories (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id     uuid NOT NULL,
            scope      text NOT NULL,
            scope_id   uuid NOT NULL,
            key        text NOT NULL,
            value      jsonb NOT NULL,
            confidence real NOT NULL DEFAULT 1.0,
            source     text,
            expires_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (scope, scope_id, key)
        );
    """)

    # ── Ops — jobs table IS the queue (§25) ──────────────────────────────────
    op.execute("""
        CREATE TABLE jobs (
            id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           uuid,
            site_id          uuid REFERENCES sites(id) ON DELETE CASCADE,
            kind             text NOT NULL,
            payload          jsonb NOT NULL DEFAULT '{}'::jsonb,
            queue            text NOT NULL DEFAULT 'default',
            priority         smallint NOT NULL DEFAULT 100,
            status           job_status NOT NULL DEFAULT 'queued',
            locked_by        text,
            locked_at        timestamptz,
            lease_expires_at timestamptz,
            attempts         smallint NOT NULL DEFAULT 0,
            max_attempts     smallint NOT NULL DEFAULT 3,
            run_after        timestamptz NOT NULL DEFAULT now(),
            progress         jsonb NOT NULL DEFAULT '{}'::jsonb,
            error            text,
            created_at       timestamptz NOT NULL DEFAULT now(),
            started_at       timestamptz,
            finished_at      timestamptz
        );
        CREATE INDEX jobs_dequeue ON jobs (queue, priority, run_after) WHERE status = 'queued';
        CREATE INDEX ON jobs (site_id, kind, created_at DESC);
        CREATE INDEX jobs_reclaim ON jobs (lease_expires_at) WHERE status = 'running';
        CREATE UNIQUE INDEX jobs_unique_pending ON jobs (site_id, kind)
            WHERE status IN ('queued','running');

        CREATE TABLE schedules (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            site_id     uuid REFERENCES sites(id) ON DELETE CASCADE,
            kind        text NOT NULL,
            cron        text NOT NULL,
            timezone    text NOT NULL DEFAULT 'Asia/Kolkata',
            payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
            is_active   boolean NOT NULL DEFAULT true,
            last_run_at timestamptz,
            next_run_at timestamptz
        );

        CREATE TABLE notifications (
            id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            user_id    uuid REFERENCES users(id) ON DELETE CASCADE,
            site_id    uuid REFERENCES sites(id) ON DELETE CASCADE,
            kind       text NOT NULL,
            title      text NOT NULL,
            body       text,
            link       text,
            severity   issue_severity NOT NULL DEFAULT 'notice',
            read_at    timestamptz,
            emailed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ON notifications (user_id, read_at NULLS FIRST, created_at DESC);

        CREATE TABLE audit_log (
            id          bigserial PRIMARY KEY,
            org_id      uuid,
            user_id     uuid,
            action      text NOT NULL,
            entity_type text,
            entity_id   uuid,
            metadata    jsonb NOT NULL DEFAULT '{}'::jsonb,
            ip          inet,
            created_at  timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ON audit_log (org_id, created_at DESC);

        CREATE TABLE reports (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL,
            site_id      uuid NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            kind         text NOT NULL,
            period_start date NOT NULL,
            period_end   date NOT NULL,
            data         jsonb NOT NULL,
            narrative    text,
            pdf_path     text,
            share_token  text UNIQUE,
            state        text NOT NULL DEFAULT 'draft',
            approved_by  uuid REFERENCES users(id),
            approved_at  timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now(),
            UNIQUE (site_id, kind, period_start)
        );

        CREATE TABLE api_keys (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            name         text NOT NULL,
            key_prefix   text NOT NULL,
            key_hash     text NOT NULL UNIQUE,
            scopes       text[] NOT NULL DEFAULT '{read}',
            last_used_at timestamptz,
            expires_at   timestamptz,
            revoked_at   timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now()
        );

        -- Reserved, unbuilt (§5 module 27). Present so hosting needs no migration.
        CREATE TABLE subscriptions (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            plan               text, status text, current_period_end timestamptz
        );
        CREATE TABLE usage_events (
            id          bigserial PRIMARY KEY,
            org_id      uuid NOT NULL,
            kind        text NOT NULL,
            quantity    numeric NOT NULL DEFAULT 1,
            occurred_at timestamptz NOT NULL DEFAULT now()
        );
    """)

    # Trigram index for the "search your queries" box. Optional — the bundled
    # pgserver build has no pg_trgm; the box falls back to LIKE without it.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
                CREATE INDEX gsc_query_trgm ON gsc_daily USING gin (query gin_trgm_ops);
            END IF;
        END
        $$;
    """)

    # ── Materialised views (§13.9) ───────────────────────────────────────────
    op.execute("""
        CREATE MATERIALIZED VIEW mv_site_kpis AS
        SELECT  s.id AS site_id, s.org_id,
                COALESCE(sum(g.clicks) FILTER (WHERE g.date >= current_date - 28), 0)
                    AS clicks_28d,
                COALESCE(sum(g.clicks) FILTER (WHERE g.date >= current_date - 56
                                                 AND g.date <  current_date - 28), 0)
                    AS clicks_prev_28d,
                COALESCE(sum(g.impressions) FILTER (WHERE g.date >= current_date - 28), 0)
                    AS impressions_28d,
                avg(g.position) FILTER (WHERE g.date >= current_date - 28)
                    AS avg_position_28d
        FROM sites s LEFT JOIN gsc_daily g ON g.site_id = s.id
        WHERE s.deleted_at IS NULL
        GROUP BY s.id, s.org_id;

        CREATE UNIQUE INDEX ON mv_site_kpis (site_id);

        CREATE MATERIALIZED VIEW mv_query_opportunities AS
        SELECT  site_id, org_id, query,
                sum(impressions) AS impressions,
                sum(clicks)      AS clicks,
                avg(position)    AS avg_position,
                sum(clicks)::real / nullif(sum(impressions),0) AS ctr
        FROM    gsc_daily
        WHERE   date >= current_date - 28
        GROUP BY site_id, org_id, query
        HAVING  avg(position) BETWEEN 5 AND 20 AND sum(impressions) > 100;

        CREATE UNIQUE INDEX ON mv_query_opportunities (site_id, query);
    """)

    # ── Row-level security (§28) ─────────────────────────────────────────────
    # FORCE so the table owner is subject to policies too — belt and braces.
    tenant_tables = [
        "clients", "sites", "portal_tokens", "oauth_connections", "sync_state",
        "gsc_daily", "ga4_daily", "lighthouse_runs", "rank_history",
        "crawls", "pages", "internal_links", "issues",
        "keyword_clusters", "competitors", "backlinks",
        "briefs", "drafts", "publications",
        "agent_runs", "embeddings", "memories",
        "jobs", "schedules", "notifications", "reports", "api_keys",
        "subscriptions", "usage_events",
    ]
    for table in tenant_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (org_id = nullif(current_setting('app.current_org_id', true), '')::uuid)
                WITH CHECK (org_id = nullif(current_setting('app.current_org_id', true), '')::uuid)
        """)

    # client_viewer is additionally scoped below org level, to one client.
    # RESTRICTIVE is load-bearing: permissive policies are OR'd together, so a
    # second permissive policy would *widen* access rather than narrow it.
    op.execute("""
        CREATE POLICY client_viewer_scope ON sites AS RESTRICTIVE FOR SELECT
            USING (
                current_setting('app.current_role', true) IS DISTINCT FROM 'client_viewer'
                OR client_id = nullif(current_setting('app.current_client_id', true), '')::uuid
            );

        CREATE POLICY client_viewer_scope ON clients AS RESTRICTIVE FOR SELECT
            USING (
                current_setting('app.current_role', true) IS DISTINCT FROM 'client_viewer'
                OR id = nullif(current_setting('app.current_client_id', true), '')::uuid
            );
    """)

    # The app role needs privileges on everything created above.
    op.execute("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO seoos_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO seoos_app;
    """)


def downgrade() -> None:
    op.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
