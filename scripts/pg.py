#!/usr/bin/env python
"""Postgres control — Docker if available, bundled binaries if not.

docs/10-deployment.md §32 specifies Docker Compose. That remains the recommended
setup. But Docker Desktop needs a GUI install and admin rights, which not every
machine has, and a tool that can't start is a tool nobody uses.

`pgserver` bundles PostgreSQL 16 + pgvector as a pip package — no daemon, no
sudo, no container runtime. Same major version, same extension, same SQL. The
application cannot tell the difference.

    python scripts/pg.py start|stop|status|url|psql
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Postgres receives the socket directory inside a `-o` options string, which is
# word-split. This project's path contains spaces ("Growleads AI SEO "), so
# postgres gets `-k /Users/kuldeep/Growleads` and dies:
#     postgres: invalid argument: "AI"
# pgserver resolves symlinks internally, so pointing a clean path at the project
# does not help — the data directory itself must be space-free.
#
# This matches the Docker setup rather than diverging from it: with Docker
# Compose (docs §32) pgdata lives in a named Docker volume, also outside the
# project folder. Either way the database's internal storage is not project
# content, and `pg_dump` in backup.sh captures it regardless of location.
PGDATA = Path.home() / ".seoos" / "pgdata"

# A symlink in the project folder so the location is discoverable from here.
PGDATA_LINK = ROOT / "data" / "pgdata"

DB_NAME = "seoos"
APP_USER = "seoos_app"
APP_PASSWORD = "seoos_local_dev"  # noqa: S105 — localhost-only dev default


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(
        ["docker", "info"], capture_output=True, check=False
    ).returncode == 0


def psql_bin() -> Path:
    """Path to the bundled psql binary."""
    import pgserver

    return Path(pgserver.__file__).parent / "pginstall" / "bin" / "psql"


def _ensure_link() -> None:
    """Real data in a space-free path; a pointer to it inside the project."""
    PGDATA.mkdir(parents=True, exist_ok=True)
    PGDATA_LINK.parent.mkdir(parents=True, exist_ok=True)
    if PGDATA_LINK.is_symlink():
        if PGDATA_LINK.resolve() == PGDATA.resolve():
            return
        PGDATA_LINK.unlink()
    elif PGDATA_LINK.exists():
        return  # a real directory is already there; leave it alone
    PGDATA_LINK.symlink_to(PGDATA, target_is_directory=True)


def _server():  # noqa: ANN202
    try:
        import pgserver
    except ImportError:
        sys.exit(
            "Neither Docker nor pgserver is available.\n"
            "  Install one:\n"
            "    • Docker Desktop  — https://docker.com  (matches docs §32)\n"
            "    • uv sync --extra localpg  — bundled Postgres, no admin needed"
        )
    _ensure_link()
    return pgserver.get_server(str(PGDATA), cleanup_mode=None)


def bootstrap(srv) -> None:  # noqa: ANN001
    """Create the database, the app role, and the extensions.

    Mirrors infra/postgres/init.sql. The app role is NOT the table owner, so RLS
    policies actually apply to it — see docs/08-infrastructure.md §28.
    """
    exists = srv.psql(f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
    if "1 row" not in exists:
        srv.psql(f"CREATE DATABASE {DB_NAME}")

    srv.psql(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{APP_USER}') THEN
                CREATE ROLE {APP_USER} LOGIN PASSWORD '{APP_PASSWORD}';
            END IF;
        END $$;
        GRANT CONNECT ON DATABASE {DB_NAME} TO {APP_USER};
        """
    )

    uri = srv.get_uri(database=DB_NAME)

    def run(stmt: str, *, required: bool) -> None:
        result = subprocess.run(
            [str(psql_bin()), uri, "-q", "-c", stmt],
            check=False, capture_output=True, text=True,
        )
        if result.returncode and required:
            raise SystemExit(f"Postgres bootstrap failed:\n  {stmt}\n{result.stderr}")

    # Only pgvector is required. gen_random_uuid() and sha256() are core in
    # Postgres 16, so the schema has no pgcrypto dependency. The rest are
    # optimisations the Docker image ships and this bundled build does not.
    run("CREATE EXTENSION IF NOT EXISTS vector", required=True)
    for ext in ("pgcrypto", "pg_trgm", "btree_gin", "citext"):
        run(f"CREATE EXTENSION IF NOT EXISTS {ext}", required=False)

    for stmt in (
        f"GRANT USAGE ON SCHEMA public TO {APP_USER}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_USER}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {APP_USER}",
    ):
        run(stmt, required=True)


def _as_app_user(admin_uri: str) -> str:
    """Rewrite an admin URI to connect as APP_USER.

    This distinction is the whole point of the seoos_app role, and getting it
    wrong is silent. RLS does not apply to superusers at all, and applies to the
    table owner only because migration 0001 sets FORCE ROW LEVEL SECURITY — so
    an app connected as either sees every organisation's rows. Nothing errors;
    the dashboard just quietly renders other tenants' clients.

    The isolation suite does not catch it, because tests/conftest.py rewrites
    the URL to seoos_app itself before testing the policies. It proves the
    policies are right, not that the application connects in a way that lets
    them apply.
    """
    scheme, _, rest = admin_uri.partition("://")
    _, _, tail = rest.partition("@") if "@" in rest else ("", "", rest)
    return f"{scheme}://{APP_USER}:{APP_PASSWORD}@{tail}"


def admin_url() -> str:
    """Owner connection. Migrations and bootstrap only — never the application.

    Alembic needs CREATE on the schema, which seoos_app deliberately lacks.
    """
    if docker_available():
        return "postgresql://seoos:seoos_local_dev@127.0.0.1:5432/seoos"

    srv = _server()
    bootstrap(srv)
    return srv.get_uri(database=DB_NAME)


def start() -> str:
    """The URL the application uses: least privilege, RLS enforced."""
    if docker_available():
        subprocess.run(
            ["docker", "compose", "up", "-d", "postgres"], cwd=ROOT, check=True
        )
        return _as_app_user("postgresql://seoos:seoos_local_dev@127.0.0.1:5432/seoos")

    return _as_app_user(admin_url())


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "start":
        print(start())

    elif cmd == "url":
        print(start())

    elif cmd == "admin-url":
        # Migrations only. setup.sh and run.sh export this as ADMIN_DATABASE_URL
        # so Alembic can CREATE, while the app keeps the least-privilege URL.
        print(admin_url())

    elif cmd == "stop":
        if docker_available():
            subprocess.run(["docker", "compose", "stop", "postgres"], cwd=ROOT, check=False)
        else:
            import pgserver

            pgserver.get_server(str(PGDATA), cleanup_mode="stop")
        print("stopped")

    elif cmd == "status":
        backend = "docker" if docker_available() else "pgserver (bundled)"
        print(f"backend: {backend}")
        try:
            print(f"url:     {start()}")
            print("status:  running")
        except Exception as exc:  # noqa: BLE001
            print(f"status:  not running ({exc})")

    elif cmd == "psql":
        srv = _server()
        subprocess.run([str(psql_bin()), srv.get_uri(database=DB_NAME)], check=False)

    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
