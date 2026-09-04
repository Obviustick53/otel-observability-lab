"""Run the versioned PostgreSQL migrations for the AWS lab."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

import psycopg2


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if configured:
        return configured
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    if not host or not user or password is None:
        raise RuntimeError("database configuration is incomplete")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "observability")
    return f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{name}"


def main() -> None:
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migrations:
        raise RuntimeError("no migration files found")
    with psycopg2.connect(database_url(), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            for migration in migrations:
                version = migration.name
                cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cursor.fetchone():
                    continue
                cursor.execute(migration.read_text(encoding="utf-8"))
                cursor.execute("INSERT INTO schema_migrations(version) VALUES (%s)", (version,))
                print(f"applied {version}")
    print(f"migration_count={len(migrations)}")


if __name__ == "__main__":
    main()
