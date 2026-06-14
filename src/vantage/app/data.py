"""Read-only data access for the dashboard.

Two kinds of thing live here:

* **Pure helpers** (``performance_summary``, ``indicator_snapshot``) that take
  plain DataFrames and compute the numbers the cards/tables show. These have no
  Streamlit or DB dependency, so they are unit-testable.
* **Cached accessors** that open a *read-only* DuckDB connection, run a query,
  and hand back a DataFrame. They are wrapped in ``st.cache_data`` so the
  terminal stays snappy and so a query during the nightly refresh (when the
  writer briefly holds the file) is served from cache instead of erroring.

The store is opened read-only and every accessor degrades to an empty frame if
the database does not exist yet (first boot, before the first refresh).
"""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable

import duckdb
import pandas as pd
import streamlit as st

from vantage import forecast
from vantage.config import Settings
from vantage.index.universe import SUBSECTORS, index_id_for
from vantage.storage.readers import current_series, index_levels, prices_wide
from vantage.transforms.signals import relative_strength, yoy, zscore

# How long a query result is reused before we hit DuckDB again. The data only
# changes once a day, so a few minutes keeps the UI instant and sidesteps the
# brief writer lock during the nightly refresh.
CACHE_TTL = 300

# Trailing window (in periods) for the indicator z-score, by frequency.
_ZSCORE_WINDOW = {"D": 252, "W": 104, "M": 36, "Q": 12, "A": 5}

# Last successful result per query, so a read that collides with the nightly
# writer lock serves slightly-stale data instead of erroring the page.
_LAST_GOOD: dict[str, pd.DataFrame] = {}


def db_path() -> str:
    return str(Settings.load().db_path)


def db_exists() -> bool:
    return Settings.load().db_path.exists()


def _run(key: str, fn: Callable[[duckdb.DuckDBPyConnection], pd.DataFrame]) -> pd.DataFrame:
    """Run `fn` against a read-only connection, resilient to the writer lock.

    DuckDB allows only one read-write process at a time, so a query that lands
    during the nightly refresh can fail to acquire the file. We retry briefly,
    then fall back to the last good result for this key.
    """
    if not db_exists():
        return pd.DataFrame()
    for attempt in range(4):
        try:
            con = duckdb.connect(db_path(), read_only=True)
            try:
                df = fn(con)
            finally:
                con.close()
            _LAST_GOOD[key] = df
            return df
        except duckdb.Error:
            time.sleep(0.4 * (attempt + 1))
    return _LAST_GOOD.get(key, pd.DataFrame())


@st.cache_data(ttl=CACHE_TTL)
def _query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a read-only query, returning an empty frame if the store is absent."""
    return _run(f"q:{sql}:{params}", lambda con: con.execute(sql, list(params)).df())


# --- catalog / health ------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL)
def series_catalog() -> pd.DataFrame:
    """Everything in series_meta: the indicator catalog plus freshness columns."""
    return _query(
        """
        SELECT source, series_id, metric_name, frequency, unit, subsector,
               first_obs, last_obs, last_fetched
        FROM series_meta
        ORDER BY subsector, metric_name
        """
    )


@st.cache_data(ttl=CACHE_TTL)
def available_indices() -> list[str]:
    df = _query("SELECT DISTINCT index_id FROM index_values ORDER BY index_id")
    return df["index_id"].tolist() if not df.empty else []


@st.cache_data(ttl=CACHE_TTL)
def securities() -> pd.DataFrame:
    return _query(
        """
        SELECT ticker, name, subsector, from_date, to_date
        FROM securities ORDER BY subsector, ticker
        """
    )


@st.cache_data(ttl=CACHE_TTL)
def price_coverage() -> pd.DataFrame:
    """Per-ticker price coverage, to spot a name that stopped updating."""
    return _query(
        """
        SELECT ticker, count(*) AS rows, min(date) AS first_date, max(date) AS last_date
        FROM prices GROUP BY ticker ORDER BY last_date, ticker
        """
    )


def health() -> dict:
    """Headline freshness numbers for the status bar."""
    cat = series_catalog()
    secs = securities()
    idx = available_indices()
    last_fetched = None
    if not cat.empty and cat["last_fetched"].notna().any():
        last_fetched = pd.to_datetime(cat["last_fetched"]).max()
    last_price = None
    cov = price_coverage()
    if not cov.empty and cov["last_date"].notna().any():
        last_price = pd.to_datetime(cov["last_date"]).max()
    return {
        "n_indicators": int(len(cat)),
        "n_securities": int(len(secs)),
        "n_indices": len(idx),
        "last_fetched": last_fetched,
        "last_price": last_price,
    }


# --- index data ------------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL)
def index_track(index_id: str) -> pd.DataFrame:
    """Index levels as a date-indexed frame (level_pr, level_tr)."""
    df = _run(f"idx:{index_id}", lambda con: index_levels(con, index_id))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


@st.cache_data(ttl=CACHE_TTL)
def latest_weights(index_id: str) -> pd.DataFrame:
    """Constituent weights at the most recent rebalance for one index."""
    return _query(
        """
        SELECT w.ticker, s.name, s.subsector, w.weight
        FROM index_weights w
        LEFT JOIN securities s USING (ticker)
        WHERE w.index_id = ?
          AND w.rebalance_date = (
              SELECT max(rebalance_date) FROM index_weights WHERE index_id = ?
          )
        ORDER BY w.weight DESC
        """,
        (index_id, index_id),
    )


@st.cache_data(ttl=CACHE_TTL)
def constituent_prices(index_id: str) -> pd.DataFrame:
    """Adjusted-close prices for the current constituents of `index_id`.

    A date-indexed wide frame (one column per current constituent). Empty if the
    index has no weights yet or no prices are stored.
    """
    weights = latest_weights(index_id)
    if weights.empty:
        return pd.DataFrame()
    tickers = set(weights["ticker"])
    px = _run("px:adj_close", lambda con: prices_wide(con, "adj_close"))
    if px.empty:
        return px
    cols = [c for c in px.columns if c in tickers]
    if not cols:
        return pd.DataFrame()
    px = px[cols].copy()
    px.index = pd.to_datetime(px.index)
    return px.sort_index()


def rebased_pair(index_id: str, benchmark_id: str, track: str = "level_tr") -> pd.DataFrame:
    """`index_id` and `benchmark_id` levels rebased to 100 at their common start.

    Columns are keyed by index id (the caller relabels for display). Empty if
    either side is missing the requested track.
    """
    a = index_track(index_id)
    b = index_track(benchmark_id)
    if a.empty or b.empty or track not in a or track not in b:
        return pd.DataFrame()
    pair = pd.concat([a[track].rename(index_id), b[track].rename(benchmark_id)], axis=1).dropna()
    if pair.empty:
        return pair
    return pair / pair.iloc[0] * 100.0


def relative_track(index_id: str, benchmark_id: str, track: str = "level_tr") -> pd.Series:
    """Relative-strength line of `index_id` vs `benchmark_id` (>100 = outperforming)."""
    a = index_track(index_id)
    b = index_track(benchmark_id)
    if a.empty or b.empty or track not in a or track not in b:
        return pd.Series(dtype=float)
    return relative_strength(a[track], b[track])


def subsector_tracks(track: str = "level_tr") -> pd.DataFrame:
    """One column per sub-sector index, rebased to 100 at their common start."""
    cols: dict[str, pd.Series] = {}
    for sub in SUBSECTORS:
        df = index_track(index_id_for(sub))
        if not df.empty and track in df:
            cols[sub] = df[track]
    if not cols:
        return pd.DataFrame()
    frame = pd.DataFrame(cols).dropna(how="all")
    frame = frame.loc[frame.dropna().index.min() :] if not frame.dropna().empty else frame
    return frame / frame.bfill().iloc[0] * 100.0


# --- forecast (per-stock next-month ARX backtest) --------------------------


def _index_level(index_id: str, track: str = "level_tr") -> pd.Series:
    """A single index level series, or empty if the index/track is missing."""
    df = index_track(index_id)
    if df.empty or track not in df:
        return pd.Series(dtype=float)
    return df[track]


@st.cache_data(ttl=CACHE_TTL)
def _exog_frame() -> pd.DataFrame:
    """All indicator series as one date-indexed frame (columns = series_id)."""
    cat = series_catalog()
    cols: dict[str, pd.Series] = {}
    for _, row in cat.iterrows():
        s = indicator_series(row["source"], row["series_id"])
        if not s.empty:
            cols[row["series_id"]] = s["value"]
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def _run_backtest(ticker: str, px: pd.DataFrame, secs: pd.DataFrame, exog) -> tuple:
    """Backtest one stock given shared, already-loaded inputs."""
    sub = secs.loc[ticker, "subsector"] if ticker in secs.index else None
    sector = _index_level(index_id_for(sub)) if sub else pd.Series(dtype=float)
    market = _index_level("VHC")
    return forecast.backtest_stock(
        px[ticker],
        exog=exog,
        sector_index=sector if not sector.empty else None,
        market_index=market if not market.empty else None,
    )


@st.cache_data(ttl=CACHE_TTL)
def forecast_backtest(ticker: str) -> tuple[pd.DataFrame, dict]:
    """Walk-forward backtest + honest metrics for one stock's next-month model."""
    px = constituent_prices("VHC")
    if px.empty or ticker not in px.columns:
        return pd.DataFrame(columns=["pred", "actual"]), forecast.metrics(pd.DataFrame())
    exog = _exog_frame()
    secs = securities().set_index("ticker")
    return _run_backtest(ticker, px, secs, exog if not exog.empty else None)


@st.cache_data(ttl=CACHE_TTL)
def forecast_leaderboard() -> pd.DataFrame:
    """Backtest metrics for every constituent, one row per stock."""
    px = constituent_prices("VHC")
    if px.empty:
        return pd.DataFrame()
    secs = securities().set_index("ticker")
    exog = _exog_frame()
    exog_arg = exog if not exog.empty else None
    rows = []
    for ticker in px.columns:
        name = secs.loc[ticker, "name"] if ticker in secs.index else ticker
        sub = secs.loc[ticker, "subsector"] if ticker in secs.index else None
        _, m = _run_backtest(ticker, px, secs, exog_arg)
        rows.append({"ticker": ticker, "name": name, "subsector": sub, **m})
    return pd.DataFrame(rows)


# --- indicator series ------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL)
def indicator_series(source: str, series_id: str) -> pd.DataFrame:
    """Current best view of one indicator (date-indexed value)."""
    df = _run(f"ser:{source}:{series_id}", lambda con: current_series(con, source, series_id))
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")


# --- pure compute helpers (unit-tested) ------------------------------------

_WINDOWS = [
    ("1D", pd.Timedelta(days=1)),
    ("1W", pd.Timedelta(days=7)),
    ("1M", pd.Timedelta(days=30)),
    ("3M", pd.Timedelta(days=91)),
    ("6M", pd.Timedelta(days=182)),
    ("YTD", None),
    ("1Y", pd.Timedelta(days=365)),
]


def _asof_value(series: pd.Series, when: pd.Timestamp) -> float | None:
    """Last value at or before `when` (point-in-time, no interpolation)."""
    s = series.dropna()
    s = s[s.index <= when]
    return float(s.iloc[-1]) if not s.empty else None


def performance_summary(series: pd.Series) -> dict[str, float | None]:
    """Trailing returns (%) of a level series over the standard windows."""
    s = series.dropna()
    if s.empty:
        return {label: None for label, _ in _WINDOWS}
    last_date = s.index[-1]
    last_val = float(s.iloc[-1])
    out: dict[str, float | None] = {}
    for label, delta in _WINDOWS:
        if label == "YTD":
            start = pd.Timestamp(year=last_date.year, month=1, day=1)
        else:
            start = last_date - delta
        base = _asof_value(s, start)
        out[label] = (last_val / base - 1.0) * 100.0 if base else None
    return out


def constituent_returns(prices: pd.DataFrame, window_days: int) -> pd.Series:
    """Per-ticker % return over the trailing `window_days`, point-in-time.

    `prices` is a date-indexed wide frame (one column per ticker). For each
    ticker the latest available price is compared to the last price at or before
    ``latest_date - window_days`` (no interpolation). Tickers without history on
    both ends are dropped. Returned sorted best-to-worst.
    """
    if prices is None or prices.empty:
        return pd.Series(dtype=float)
    frame = prices.sort_index()
    start = frame.index.max() - pd.Timedelta(days=window_days)
    out: dict[str, float] = {}
    for ticker in frame.columns:
        s = frame[ticker].dropna()
        if s.empty:
            continue
        base = _asof_value(s, start)
        if not base:  # None or 0 -> no usable base price
            continue
        out[ticker] = (float(s.iloc[-1]) / base - 1.0) * 100.0
    return pd.Series(out, dtype=float).sort_values(ascending=False)


def indicator_snapshot(series: pd.Series, frequency: str | None) -> dict:
    """Latest value, YoY %, trailing z-score, and a sparkline tail for a card."""
    s = series.dropna()
    if s.empty:
        return {"latest": None, "yoy": None, "zscore": None, "spark": pd.Series(dtype=float)}
    window = _ZSCORE_WINDOW.get((frequency or "M"), 36)
    yoy_s = yoy(s)
    z = zscore(s, window)
    return {
        "latest": float(s.iloc[-1]),
        "as_of": s.index[-1],
        "yoy": float(yoy_s.iloc[-1]) if pd.notna(yoy_s.iloc[-1]) else None,
        "zscore": float(z.iloc[-1]) if pd.notna(z.iloc[-1]) else None,
        "spark": s.tail(60),
    }


def staleness(last_obs, frequency: str | None, today: dt.date | None = None) -> bool:
    """True if a series looks stale given its frequency (loose, freshness hint)."""
    if last_obs is None or pd.isna(last_obs):
        return True
    today = today or dt.date.today()
    last = pd.to_datetime(last_obs).date()
    budget = {"D": 7, "W": 21, "M": 75, "Q": 200, "A": 500}.get(frequency or "M", 75)
    return (today - last).days > budget
