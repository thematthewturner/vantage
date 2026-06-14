"""End-to-end wiring test: seed prices -> build indices -> read levels.

Uses synthetic prices (no network) so it runs offline, exercising the storage
schema, the build-all orchestration, and the readers together.
"""

import pandas as pd

from vantage.index.subsectors import build_all_indices
from vantage.storage.readers import index_levels
from vantage.storage.writers import upsert_prices, upsert_securities


def _seed(con):
    upsert_securities(
        con,
        [
            {"ticker": "LLY", "name": "Eli Lilly", "subsector": "pharma", "from": "2020-01-01"},
            {"ticker": "UNH", "name": "UnitedHealth", "subsector": "payers", "from": "2020-01-01"},
        ],
    )
    dates = pd.bdate_range("2020-01-01", periods=10)
    rows = []
    for i, d in enumerate(dates):
        rows.append(
            {
                "ticker": "XLV",
                "date": d.date(),
                "close": 50.0 + i,
                "adj_close": 50.0 + i * 1.5,
                "shares_out": 10_000.0,
            }
        )
        rows.append(
            {
                "ticker": "LLY",
                "date": d.date(),
                "close": 100.0 + i,
                "adj_close": 100.0 + i,
                "shares_out": 1_000.0,
            }
        )
        rows.append(
            {
                "ticker": "UNH",
                "date": d.date(),
                "close": 200.0 + 2 * i,
                "adj_close": 200.0 + 2 * i,
                "shares_out": 900.0,
            }
        )
    upsert_prices(con, pd.DataFrame(rows))


def test_build_all_indices_end_to_end(con, settings, monkeypatch):
    # universe.toml lists the full set; restrict to our two seeded names.
    import vantage.index.universe as universe

    monkeypatch.setattr(
        universe,
        "load_universe",
        lambda: [
            {"ticker": "LLY", "subsector": "pharma", "from": "2020-01-01"},
            {"ticker": "UNH", "subsector": "payers", "from": "2020-01-01"},
        ],
    )
    _seed(con)

    built = build_all_indices(con, settings)
    assert "BASE_XLV" in built
    assert "VHC" in built
    assert "VHC_PHARMA" in built and "VHC_PAYERS" in built

    baseline = index_levels(con, "BASE_XLV")
    assert len(baseline) == 10
    assert abs(baseline["level_pr"].iloc[0] - 100.0) < 1e-9

    whole = index_levels(con, "VHC")
    assert len(whole) == 10
    assert abs(whole["level_pr"].iloc[0] - 100.0) < 1e-9  # base value
    assert whole["level_pr"].iloc[-1] > 100.0  # both names rose

    # Single-name sub-index equals that name's normalized price path.
    pharma = index_levels(con, "VHC_PHARMA")
    assert abs(pharma["level_pr"].iloc[-1] - 100.0 * (109.0 / 100.0)) < 1e-9


def test_refresh_main_runs_without_network(con, settings, monkeypatch, tmp_path):
    """refresh.main completes (and reports errors) even with no keys/network."""
    import vantage.pipeline.refresh as refresh

    monkeypatch.setattr(refresh.Settings, "load", staticmethod(lambda: settings))
    # No FRED key and yfinance/network absent -> sources error but run completes.
    rc = refresh.main(["--no-prices"])
    assert rc in (0, 1)  # non-zero if FRED key missing; must not raise
