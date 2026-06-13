"""Equity price connector backed by yfinance.

Prices have a different shape than indicator observations (one row per
ticker/day with close, adjusted close, and shares outstanding), so this is a
standalone fetcher rather than a ``Connector`` subclass.

Everything yfinance-specific lives here on purpose: its terms of service are
murky and it breaks without notice, so swapping to Tiingo/Polygon/Stooq later
should be a single-file change. yfinance is an optional dependency and is
imported lazily so the rest of the package imports cleanly without it.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd

PRICE_COLUMNS = ["ticker", "date", "close", "adj_close", "shares_out"]


def _shares_outstanding(ticker_obj, index: pd.DatetimeIndex) -> pd.Series:
    """Best-effort historical shares outstanding aligned to `index`.

    Tries yfinance's historical share count; falls back to the current static
    value applied across all dates. The static fallback is an approximation
    that biases cap weights for names whose share count changed materially --
    a documented limitation, refined when a fundamentals source lands.
    """
    shares = None
    try:
        hist = ticker_obj.get_shares_full(start=index.min(), end=index.max())
        if hist is not None and len(hist) > 0:
            shares = hist[~hist.index.duplicated(keep="last")]
            shares = shares.reindex(index, method="ffill")
    except Exception:
        shares = None

    if shares is None or shares.isna().all():
        static = (ticker_obj.info or {}).get("sharesOutstanding")
        shares = pd.Series(static, index=index, dtype="float64")
    return shares.astype("float64")


def fetch_prices(tickers: list[str], start: dt.date) -> pd.DataFrame:
    """Return daily prices for `tickers` since `start` in canonical long format.

    Columns: ticker, date, close, adj_close, shares_out.
    """
    import yfinance as yf

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        tk = yf.Ticker(ticker)
        hist = tk.history(start=start.isoformat(), auto_adjust=False)
        if hist.empty:
            continue
        idx = hist.index
        df = pd.DataFrame(
            {
                "ticker": ticker,
                "date": idx.tz_localize(None).date if idx.tz is not None else idx.date,
                "close": hist["Close"].to_numpy(),
                "adj_close": hist["Adj Close"].to_numpy(),
                "shares_out": _shares_outstanding(tk, idx).to_numpy(),
            }
        )
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    return pd.concat(frames, ignore_index=True)[PRICE_COLUMNS]
