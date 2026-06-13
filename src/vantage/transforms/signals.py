"""Derived indicator signals.

All transforms are pure and use only trailing information -- never centered
windows or forward fills past the last known print -- so a signal computed at
time t could actually have been computed at time t (no lookahead).
"""

from __future__ import annotations

import pandas as pd

# periods per year by pandas-inferred frequency, for period-aware YoY
_PERIODS_PER_YEAR = {
    "D": 252,
    "B": 252,
    "W": 52,
    "M": 12,
    "MS": 12,
    "Q": 4,
    "QS": 4,
    "A": 1,
    "AS": 1,
    "Y": 1,
    "YS": 1,
}


def _periods_per_year(series: pd.Series, default: int = 12) -> int:
    freq = pd.infer_freq(series.index) if series.index.is_monotonic_increasing else None
    if freq is None:
        return default
    return _PERIODS_PER_YEAR.get(freq.split("-")[0], default)


def yoy(series: pd.Series, periods: int | None = None) -> pd.Series:
    """Year-over-year percent change. Period count inferred from the index."""
    n = periods or _periods_per_year(series)
    return series.pct_change(n)


def mom(series: pd.Series) -> pd.Series:
    return series.pct_change(1)


def qoq(series: pd.Series) -> pd.Series:
    return series.pct_change(1)


def zscore(series: pd.Series, window: int) -> pd.Series:
    """Rolling z-score over a trailing window (explicit window = no hidden lookahead)."""
    roll = series.rolling(window)
    return (series - roll.mean()) / roll.std()


def smooth(series: pd.Series, window: int) -> pd.Series:
    """Trailing moving average (never centered)."""
    return series.rolling(window).mean()


def diffusion(frame: pd.DataFrame) -> pd.Series:
    """Breadth: share of component series rising vs the prior period (0..1)."""
    rising = frame.diff() > 0
    return rising.sum(axis=1) / frame.notna().sum(axis=1)
