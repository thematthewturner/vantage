import pandas as pd

from vantage.index.baselines import BASELINE_INDEXES, baseline_tickers, build_baseline_index


def test_build_baseline_uses_full_history_without_custom_base_date_filter():
    prices = pd.DataFrame(
        [
            {"ticker": "XLV", "date": "1998-12-22", "close": 10.0, "adj_close": 5.0},
            {"ticker": "XLV", "date": "2020-01-02", "close": 15.0, "adj_close": 10.0},
            {"ticker": "UNH", "date": "2020-01-02", "close": 20.0, "adj_close": 20.0},
        ]
    )

    levels = build_baseline_index("BASE_XLV", "XLV", prices, base_value=100.0)

    assert levels["date"].tolist() == [
        pd.Timestamp("1998-12-22").date(),
        pd.Timestamp("2020-01-02").date(),
    ]
    assert levels["level_pr"].tolist() == [100.0, 150.0]
    assert levels["level_tr"].tolist() == [100.0, 200.0]


def test_baseline_tickers_match_configured_indexes():
    assert set(baseline_tickers()) == {meta["ticker"] for meta in BASELINE_INDEXES.values()}
    assert {"XLV", "IYH", "VHT"}.issubset(set(baseline_tickers()))
