"""Upsert helpers. All writes are keyed by primary key so re-runs are idempotent."""

from __future__ import annotations

import duckdb
import pandas as pd

from vantage.schema import Observation, SeriesMeta


def upsert_series_meta(con: duckdb.DuckDBPyConnection, meta: SeriesMeta,
                       first_obs=None, last_obs=None) -> None:
    con.execute(
        """
        INSERT INTO series_meta
            (source, series_id, metric_name, frequency, unit, subsector, notes,
             first_obs, last_obs, last_fetched)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, now())
        ON CONFLICT (source, series_id) DO UPDATE SET
            metric_name = excluded.metric_name,
            frequency   = excluded.frequency,
            unit        = excluded.unit,
            subsector   = excluded.subsector,
            notes       = excluded.notes,
            first_obs   = excluded.first_obs,
            last_obs    = excluded.last_obs,
            last_fetched = now()
        """,
        [meta.source, meta.series_id, meta.metric_name, meta.frequency.value,
         meta.unit, meta.subsector, meta.notes, first_obs, last_obs],
    )


def upsert_observations(con: duckdb.DuckDBPyConnection, observations: list[Observation]) -> int:
    """Insert observations, accumulating vintages (no clobber of prior as_of rows)."""
    if not observations:
        return 0
    rows = [(o.source, o.series_id, o.date, o.as_of, o.value) for o in observations]
    con.executemany(
        """
        INSERT INTO observations (source, series_id, date, as_of, value)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (source, series_id, date, as_of) DO UPDATE SET
            value = excluded.value
        """,
        rows,
    )
    return len(rows)


def upsert_prices(con: duckdb.DuckDBPyConnection, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    con.register("_prices_in", frame)
    con.execute(
        """
        INSERT INTO prices (ticker, date, close, adj_close, shares_out)
        SELECT ticker, date, close, adj_close, shares_out FROM _prices_in
        ON CONFLICT (ticker, date) DO UPDATE SET
            close = excluded.close,
            adj_close = excluded.adj_close,
            shares_out = excluded.shares_out
        """
    )
    con.unregister("_prices_in")
    return len(frame)


def upsert_securities(con: duckdb.DuckDBPyConnection, securities: list[dict]) -> int:
    for sec in securities:
        con.execute(
            """
            INSERT INTO securities (ticker, name, subsector, from_date, to_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (ticker) DO UPDATE SET
                name = excluded.name,
                subsector = excluded.subsector,
                from_date = excluded.from_date,
                to_date = excluded.to_date,
                notes = excluded.notes
            """,
            [sec["ticker"], sec.get("name"), sec.get("subsector"),
             sec.get("from") or None, sec.get("to") or None, sec.get("notes")],
        )
    return len(securities)


def write_index(con: duckdb.DuckDBPyConnection, index_id: str,
                levels: pd.DataFrame, weights: pd.DataFrame) -> None:
    """Replace stored values/weights for one index id (full recompute each build)."""
    con.execute("DELETE FROM index_values WHERE index_id = ?", [index_id])
    con.execute("DELETE FROM index_weights WHERE index_id = ?", [index_id])
    if not levels.empty:
        con.register("_lv", levels)
        con.execute(
            "INSERT INTO index_values (index_id, date, level_pr, level_tr) "
            "SELECT ?, date, level_pr, level_tr FROM _lv", [index_id]
        )
        con.unregister("_lv")
    if not weights.empty:
        con.register("_wt", weights)
        con.execute(
            "INSERT INTO index_weights (index_id, rebalance_date, ticker, weight) "
            "SELECT ?, rebalance_date, ticker, weight FROM _wt", [index_id]
        )
        con.unregister("_wt")
