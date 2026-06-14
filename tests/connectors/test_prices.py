"""Offline tests for the price sanitizer (no network / no yfinance import)."""

import pandas as pd

from vantage.connectors.prices_yf import sanitize_prices


def _frame(rows):
    return pd.DataFrame(rows, columns=["ticker", "date", "close", "adj_close", "shares_out"])


def test_sanitize_keeps_valid_rows():
    frame = _frame(
        [
            ["LLY", "2020-01-02", 100.0, 100.0, 1000.0],
            ["UNH", "2020-01-02", 200.0, 198.0, 900.0],
        ]
    )
    clean, rejected = sanitize_prices(frame)
    assert len(clean) == 2
    assert rejected.empty


def test_sanitize_drops_nonpositive_and_null_prices():
    frame = _frame(
        [
            ["LLY", "2020-01-02", 100.0, 100.0, 1000.0],  # good
            ["BAD", "2020-01-02", 0.0, 50.0, 100.0],  # zero close -> inf return
            ["NEG", "2020-01-02", -5.0, 50.0, 100.0],  # negative close
            ["NUL", "2020-01-02", 50.0, None, 100.0],  # null adj_close
        ]
    )
    clean, rejected = sanitize_prices(frame)
    assert clean["ticker"].tolist() == ["LLY"]
    assert set(rejected["ticker"]) == {"BAD", "NEG", "NUL"}
    assert "reason" in rejected.columns
    assert rejected.set_index("ticker").loc["NUL", "reason"] == "non-positive or null adj_close"


def test_sanitize_empty_frame():
    clean, rejected = sanitize_prices(_frame([]))
    assert clean.empty
    assert rejected.empty
    assert "reason" in rejected.columns
