"""Print the layered safety-index ranking. Reads metric_safety_index from
the warehouse and renders it as a wide table grouped by recommendation
bucket. Run after `dbt build` lands."""

from __future__ import annotations

from pathlib import Path

import duckdb
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "vantage.duckdb"


def fmt(v: float | None, spec: str = "{:.2f}") -> str:
    if v is None:
        return "—"
    try:
        return spec.format(float(v))
    except (ValueError, TypeError):
        return str(v)


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    rows = con.execute(
        """
        SELECT
            safety_rank,
            ticker,
            business_model,
            market_cap,
            enterprise_value,
            ev_to_revenue,
            ev_to_ebitda,
            ev_to_fcf,
            fcf_yield,
            species_overall,
            dcf_verdict,
            implied_5yr_cagr,
            growth_gap,
            quality_rank,
            quality_score,
            guidance_adjusted_margin_of_safety,
            risk_score,
            demanded_margin_of_safety,
            graham_overall,
            combined_safety_score,
            recommendation_bucket
        FROM metric_safety_index
        ORDER BY combined_safety_score DESC, ticker
        """
    ).fetchall()
    con.close()

    console = Console(width=200)
    table = Table(
        title="VANTAGE Safety Index — layered Graham-spirited ranking (22 publics)",
        show_lines=False,
        header_style="bold",
    )
    table.add_column("#", justify="right")
    table.add_column("Ticker")
    table.add_column("Species", style="dim")
    table.add_column("MktCap", justify="right")
    table.add_column("EV", justify="right")
    table.add_column("EV/Rev", justify="right")
    table.add_column("EV/EBITDA", justify="right")
    table.add_column("EV/FCF", justify="right")
    table.add_column("FCF Yld", justify="right")
    table.add_column("#1 Species", justify="center")
    table.add_column("#2 DCF", justify="center")
    table.add_column("Impl/Obs Growth", justify="right")
    table.add_column("#3 Qual", justify="right")
    table.add_column("#4 G-MoS", justify="right")
    table.add_column("#5 Risk", justify="right")
    table.add_column("Graham", justify="center", style="dim")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Bucket", justify="left")

    bucket_color = {
        "quality_and_cushion": "green",
        "watch_list": "cyan",
        "neutral": "white",
        "avoid_or_special_view_required": "red",
    }

    for r in rows:
        (
            rank, ticker, species, mkt_cap, ev,
            ev_rev, ev_ebitda, ev_fcf, fcf_yld,
            species_verdict, dcf_verdict,
            implied_g, growth_gap,
            qual_rank, qual_score,
            g_mos, risk_score, demanded_mos,
            graham, score, bucket,
        ) = r
        table.add_row(
            str(rank),
            ticker or "—",
            species or "—",
            fmt(mkt_cap, "{:,.0f}"),
            fmt(ev, "{:,.0f}"),
            fmt(ev_rev),
            fmt(ev_ebitda),
            fmt(ev_fcf),
            fmt(float(fcf_yld) * 100 if fcf_yld is not None else None, "{:.1f}%"),
            species_verdict or "—",
            dcf_verdict or "—",
            f"{fmt(float(implied_g)*100 if implied_g is not None else None, '{:.0f}%')}"
            f" / "
            f"{fmt(float(growth_gap)*100 + float(implied_g)*100 if (growth_gap is not None and implied_g is not None) else None, '{:.0f}%')}",
            f"#{qual_rank} ({fmt(qual_score)})" if qual_rank else "—",
            fmt(float(g_mos) * 100 if g_mos is not None else None, "{:+.0f}%"),
            f"{fmt(risk_score)} ({demanded_mos or '—'})",
            graham or "—",
            fmt(score, "{:+.2f}"),
            f"[{bucket_color.get(bucket, 'white')}]{bucket}[/{bucket_color.get(bucket, 'white')}]",
        )

    console.print(table)
    console.print()
    console.print(
        "[dim]Reading order: #1 species ceiling pass/fail · #2 reverse-DCF verdict · "
        "#3 quality cross-section rank · #4 guidance-adjusted margin of safety · "
        "#5 risk score (lower = tighter cushion required). "
        "Graham column = pure 1973 screen (every name fails — that's the point).[/dim]"
    )


if __name__ == "__main__":
    main()
