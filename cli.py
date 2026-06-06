"""VANTAGE CLI. Phase 0 wires `init` (create DuckDB file) and `build` (run dbt).
Later phases add `ingest`, `prospectus`, `report`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import duckdb
import typer
from rich.console import Console

from vantage_config import REPO_ROOT, settings

app = typer.Typer(help="VANTAGE — Digital Health Intelligence Engine")
console = Console()


@app.command()
def init() -> None:
    """Create the DuckDB file if it doesn't exist."""
    path = Path(settings.duckdb_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    con.execute("SELECT 1").fetchone()
    con.close()
    console.print(f"[green]ok[/green] DuckDB ready at {path}")


@app.command()
def build(full_refresh: bool = typer.Option(False, "--full-refresh")) -> None:
    """Run `dbt build` against the VANTAGE project (seeds + models + tests)."""
    dbt_dir = REPO_ROOT / "dbt_vantage"
    cmd = [
        "dbt",
        "build",
        "--project-dir",
        str(dbt_dir),
        "--profiles-dir",
        str(dbt_dir),
    ]
    if full_refresh:
        cmd.append("--full-refresh")
    console.print(f"[cyan]→[/cyan] {' '.join(cmd)}")
    sys.exit(subprocess.call(cmd))


@app.command()
def ingest(_source: str = typer.Argument(..., help="sec|cms|news|secondary")) -> None:
    """Run an ingestion adapter. Wired in Phase 1+."""
    console.print("[yellow]ingest[/yellow] not implemented yet (Phase 1+)")
    raise typer.Exit(code=2)


@app.command()
def prospectus(_company_id: str = typer.Argument(...)) -> None:
    """Generate an investment memo for a company. Wired in Phase 5."""
    console.print("[yellow]prospectus[/yellow] not implemented yet (Phase 5)")
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
