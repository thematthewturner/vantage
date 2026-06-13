"""DuckDB connection management and migration runner."""

from __future__ import annotations

from pathlib import Path

import duckdb

from vantage.config import REPO_ROOT, Settings

MIGRATIONS_DIR = REPO_ROOT / "migrations"


def connect(
    settings: Settings | None = None, *, read_only: bool = False
) -> duckdb.DuckDBPyConnection:
    """Open (creating if needed) the DuckDB store and ensure the schema exists."""
    settings = settings or Settings.load()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.db_path), read_only=read_only)
    if not read_only:
        run_migrations(con)
    return con


def run_migrations(con: duckdb.DuckDBPyConnection, migrations_dir: Path | None = None) -> None:
    """Apply every .sql file in order. Migrations are written idempotently."""
    migrations_dir = migrations_dir or MIGRATIONS_DIR
    for path in sorted(migrations_dir.glob("*.sql")):
        con.execute(path.read_text())
