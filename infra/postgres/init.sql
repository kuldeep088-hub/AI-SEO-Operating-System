-- Runs once on first container start, before migrations.
-- Extensions must exist before Alembic creates tables that use them.

CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid(), digest()
CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- trigram search on queries/URLs
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS citext;      -- case-insensitive email

-- The application connects as this role. It is NOT superuser and NOT the table
-- owner, so RLS policies actually apply to it. The `seoos` bootstrap role owns
-- the schema; table owners bypass RLS unless FORCE is set, which the migration
-- does as a second line of defence. See docs/08-infrastructure.md §28.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'seoos_app') THEN
        CREATE ROLE seoos_app LOGIN PASSWORD 'seoos_local_dev';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE seoos TO seoos_app;
GRANT USAGE ON SCHEMA public TO seoos_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO seoos_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO seoos_app;
