"""Typed query helpers, including the point-in-time ASOF lookups."""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd


def last_obs_date(con: duckdb.DuckDBPyConnection, source: str, series_id: str) -> dt.date | None:
    """Latest period stored for a series, to drive incremental fetches."""
    row = con.execute(
        "SELECT max(date) FROM observations WHERE source = ? AND series_id = ?",
        [source, series_id],
    ).fetchone()
    return row[0] if row and row[0] is not None else None


def current_series(con: duckdb.DuckDBPyConnection, source: str, series_id: str) -> pd.DataFrame:
    """Current best view of a series: latest vintage per period. Columns: date, value."""
    return con.execute(
        """
        SELECT date, value FROM observations
        WHERE source = ? AND series_id = ?
        QUALIFY row_number() OVER (PARTITION BY date ORDER BY as_of DESC) = 1
        ORDER BY date
        """,
        [source, series_id],
    ).df()


def series_as_known_on(
    con: duckdb.DuckDBPyConnection, source: str, series_id: str, known_date: dt.date
) -> pd.DataFrame:
    """Point-in-time view: each period's value as it was knowable on `known_date`.

    Uses only vintages published on or before `known_date`, so backtests never
    see a revision they could not have had. Columns: date, value.
    """
    return con.execute(
        """
        SELECT date, value FROM observations
        WHERE source = ? AND series_id = ? AND as_of <= ?
        QUALIFY row_number() OVER (PARTITION BY date ORDER BY as_of DESC) = 1
        ORDER BY date
        """,
        [source, series_id, known_date],
    ).df()


def prices_wide(con: duckdb.DuckDBPyConnection, value: str = "adj_close") -> pd.DataFrame:
    """Pivot prices to date-indexed wide frame (one column per ticker)."""
    if value not in {"close", "adj_close", "shares_out"}:
        raise ValueError(f"unexpected price column: {value!r}")
    long = con.execute(f"SELECT date, ticker, {value} AS v FROM prices ORDER BY date").df()
    if long.empty:
        return long
    return long.pivot(index="date", columns="ticker", values="v")


def index_levels(con: duckdb.DuckDBPyConnection, index_id: str) -> pd.DataFrame:
    return con.execute(
        "SELECT date, level_pr, level_tr FROM index_values WHERE index_id = ? ORDER BY date",
        [index_id],
    ).df()
