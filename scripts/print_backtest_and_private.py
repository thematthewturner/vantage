"""Print the safety-index backtest (bucket transitions across snapshots)
and the parallel private-corpus ranking. Run after `dbt build`."""

from __future__ import annotations

from pathlib import Path

import duckdb
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "vantage.duckdb"


def fmt(v: float | int | None, spec: str = "{:.2f}") -> str:
    if v is None:
        return "—"
    try:
        return spec.format(float(v))
    except (ValueError, TypeError):
        return str(v)


def print_transitions(con: duckdb.DuckDBPyConnection, console: Console) -> None:
    rows = con.execute(
        """
        SELECT ticker, from_date, to_date, from_bucket, to_bucket,
               from_score, to_score, score_delta, price_change_pct, transition
        FROM metric_safety_index_transitions
        ORDER BY transition, ticker, from_date
        """
    ).fetchall()

    table = Table(
        title="Safety-Index Backtest — bucket transitions across snapshots",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("Ticker")
    table.add_column("From → To Date")
    table.add_column("From Bucket")
    table.add_column("To Bucket")
    table.add_column("Score", justify="right")
    table.add_column("Δ Score", justify="right")
    table.add_column("Δ Price", justify="right")
    table.add_column("Transition")

    color = {
        "rerated_up": "green",
        "rerated_down": "red",
        "unchanged": "dim",
        "mixed": "yellow",
    }
    for r in rows:
        (ticker, fd, td, fb, tb, fs, ts, ds, dp, tr) = r
        if tr == "unchanged":
            continue  # printed in summary line below
        table.add_row(
            ticker,
            f"{fd} → {td}",
            fb,
            tb,
            f"{fmt(fs, '{:+.2f}')} → {fmt(ts, '{:+.2f}')}",
            fmt(ds, "{:+.2f}"),
            fmt(float(dp) * 100 if dp is not None else None, "{:+.1f}%"),
            f"[{color.get(tr, 'white')}]{tr}[/{color.get(tr, 'white')}]",
        )

    n_unchanged = sum(1 for r in rows if r[-1] == "unchanged")
    console.print(table)
    console.print(f"[dim]({n_unchanged} unchanged rows omitted)[/dim]")


def print_private(con: duckdb.DuckDBPyConnection, console: Console) -> None:
    rows = con.execute(
        """
        SELECT private_rank, company_id, segment, cumulative_equity,
               primary_mark, valuation_per_dollar_raised,
               secondary_to_primary_delta, months_since_last_round,
               private_verdict
        FROM metric_private_safety_index
        ORDER BY private_rank
        """
    ).fetchall()

    table = Table(
        title="Private Safety Index — capital efficiency × mark freshness",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("#", justify="right")
    table.add_column("Company")
    table.add_column("Segment", style="dim")
    table.add_column("$ Equity", justify="right")
    table.add_column("Last Mark $", justify="right")
    table.add_column("Val/Equity", justify="right")
    table.add_column("Sec vs Primary", justify="right")
    table.add_column("Mo Since", justify="right")
    table.add_column("Verdict")

    color = {
        "capital_efficient_fresh_mark": "green",
        "capital_efficient_stale_mark": "cyan",
        "capital_heavy": "yellow",
        "capital_heavy_secondary_discount": "red",
        "data_unavailable": "dim",
        "mixed": "white",
    }
    for r in rows:
        (rk, cid, seg, equity, mark, vpd, sec_delta, mo, verdict) = r
        table.add_row(
            str(rk),
            cid,
            seg or "—",
            fmt(equity, "{:,.0f}"),
            fmt(mark, "{:,.0f}"),
            fmt(vpd, "{:.1f}x"),
            fmt(float(sec_delta) * 100 if sec_delta is not None else None, "{:+.0f}%"),
            str(mo) if mo is not None else "—",
            f"[{color.get(verdict, 'white')}]{verdict}[/{color.get(verdict, 'white')}]",
        )

    console.print(table)


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    console = Console(width=180)
    print_transitions(con, console)
    console.print()
    print_private(con, console)
    con.close()


if __name__ == "__main__":
    main()
