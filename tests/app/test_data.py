"""Unit tests for the dashboard's pure compute helpers (no DB, no Streamlit run)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from vantage.app import data


def _daily_level(start="2023-01-01", days=400, rate=0.0005) -> pd.Series:
    idx = pd.date_range(start, periods=days, freq="D")
    return pd.Series(100.0 * np.exp(np.arange(days) * rate), index=idx)


def test_performance_summary_windows_and_sign():
    s = _daily_level()
    perf = data.performance_summary(s)
    # Steady uptrend -> every trailing return is positive.
    for label in ["1D", "1M", "3M", "YTD", "1Y"]:
        assert perf[label] is not None
        assert perf[label] > 0
    # Longer windows capture more compounding.
    assert perf["1Y"] > perf["1M"]


def test_performance_summary_empty():
    perf = data.performance_summary(pd.Series(dtype=float))
    assert all(v is None for v in perf.values())


def test_indicator_snapshot_yoy_and_fields():
    idx = pd.date_range("2018-01-01", periods=48, freq="MS")
    s = pd.Series(np.linspace(100, 200, 48), index=idx)
    snap = data.indicator_snapshot(s, "M")
    assert snap["latest"] == 200
    # Values rose over the trailing year, so YoY is positive.
    assert snap["yoy"] is not None and snap["yoy"] > 0
    assert not snap["spark"].empty


def test_indicator_snapshot_empty():
    snap = data.indicator_snapshot(pd.Series(dtype=float), "M")
    assert snap["latest"] is None and snap["yoy"] is None


def test_staleness():
    today = dt.date(2026, 6, 13)
    fresh = dt.date(2026, 5, 1)
    old = dt.date(2025, 1, 1)
    assert data.staleness(fresh, "M", today=today) is False
    assert data.staleness(old, "M", today=today) is True
    assert data.staleness(None, "M", today=today) is True
