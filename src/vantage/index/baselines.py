"""Healthcare benchmark index baselines built from traded ETF price histories.

The custom VHC universe is useful, but it needs an external baseline so analyses
can distinguish healthcare-sector beta from constituent/sub-sector effects.  We
store each benchmark in the same ``index_values`` table as the custom indexes,
normalised to the configured base value on the first available historical date.
"""

from __future__ import annotations

import pandas as pd

# Broad, liquid U.S. healthcare sector ETFs with long public price histories.
# The keys are the canonical index ids written to index_values.
BASELINE_INDEXES: dict[str, dict[str, str]] = {
    "BASE_XLV": {
        "ticker": "XLV",
        "name": "Health Care Select Sector SPDR Fund",
    },
    "BASE_IYH": {
        "ticker": "IYH",
        "name": "iShares U.S. Healthcare ETF",
    },
    "BASE_VHT": {
        "ticker": "VHT",
        "name": "Vanguard Health Care ETF",
    },
}


def baseline_tickers() -> list[str]:
    """Tickers needed to build external healthcare benchmark baselines."""
    return [meta["ticker"] for meta in BASELINE_INDEXES.values()]


def build_baseline_index(
    index_id: str,
    ticker: str,
    prices: pd.DataFrame,
    *,
    base_value: float = 100.0,
) -> pd.DataFrame:
    """Build a full-history normalized benchmark series from one traded ticker.

    ``close`` is used for the price-return track and ``adj_close`` for the
    total-return track.  No configured inception date is applied here: baselines
    intentionally start at the first available historical price so downstream
    comparisons have the maximum possible context.
    """
    frame = prices[prices["ticker"] == ticker].copy()
    if frame.empty:
        return pd.DataFrame(columns=["date", "level_pr", "level_tr"])

    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    frame = frame.dropna(subset=["close", "adj_close"])
    frame = frame[(frame["close"] > 0) & (frame["adj_close"] > 0)]
    if frame.empty:
        return pd.DataFrame(columns=["date", "level_pr", "level_tr"])

    first_close = float(frame["close"].iloc[0])
    first_adj = float(frame["adj_close"].iloc[0])
    return pd.DataFrame(
        {
            "date": frame["date"].dt.date,
            "level_pr": base_value * frame["close"].astype("float64") / first_close,
            "level_tr": base_value * frame["adj_close"].astype("float64") / first_adj,
        }
    )
