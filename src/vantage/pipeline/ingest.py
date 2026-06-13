"""Ingestion: pull each connector's series and the equity universe into the store.

Incremental and idempotent: each series resumes from its last stored period, and
every write is an upsert keyed by primary key. One failing source never aborts
the others -- failures are collected and reported.
"""

from __future__ import annotations

import logging

import duckdb

from vantage.config import Settings, load_universe
from vantage.connectors import REGISTRY
from vantage.connectors.prices_yf import fetch_prices
from vantage.index.universe import tickers
from vantage.storage import raw, writers
from vantage.storage.readers import last_obs_date

log = logging.getLogger("vantage.ingest")


def ingest_indicators(con: duckdb.DuckDBPyConnection, settings: Settings | None = None) -> dict:
    """Run every registered indicator connector. Returns per-series counts and errors."""
    settings = settings or Settings.load()
    results: dict[str, int] = {}
    errors: dict[str, str] = {}

    for name, connector_cls in REGISTRY.items():
        connector = connector_cls()
        for meta in connector.list_series():
            key = f"{name}:{meta.series_id}"
            try:
                since = last_obs_date(con, meta.source, meta.series_id)
                payload, observations = connector.run(meta.series_id, since=since)
                raw.land(meta.source, meta.series_id, payload, settings)
                n = writers.upsert_observations(con, observations)
                first, last = con.execute(
                    "SELECT min(date), max(date) FROM observations "
                    "WHERE source = ? AND series_id = ?",
                    [meta.source, meta.series_id],
                ).fetchone()
                writers.upsert_series_meta(con, meta, first_obs=first, last_obs=last)
                results[key] = n
            except Exception as exc:  # one bad series doesn't sink the run
                errors[key] = str(exc)
                log.warning("indicator ingest failed for %s: %s", key, exc)
    return {"counts": results, "errors": errors}


def ingest_prices(con: duckdb.DuckDBPyConnection, settings: Settings | None = None) -> dict:
    """Fetch and store equity prices for the configured universe."""
    settings = settings or Settings.load()
    writers.upsert_securities(con, load_universe())
    try:
        frame = fetch_prices(tickers(), settings.index_base_date)
        n = writers.upsert_prices(con, frame)
        return {"rows": n, "errors": {}}
    except Exception as exc:
        log.warning("price ingest failed: %s", exc)
        return {"rows": 0, "errors": {"prices": str(exc)}}
