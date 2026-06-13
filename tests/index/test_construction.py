"""Golden-value test for the cap-weighted index.

Toy universe of two names, hand-computed:

  shares: A=10, B=10 (constant); no dividends (adj_close == close).
  day0: A=10, B=20 -> caps 100/200, weights 1/3 and 2/3, level = 100.
  day1: A 10->11 (+10%), B flat. value = 3.333*11 + 3.333*20 = 103.3333.
  day2: A flat, B 20->22 (+10%). value = 3.333*11 + 3.333*22 = 110.0.

(Units held are fixed between rebalances, so the level is just the portfolio's
market value rebased to 100 at inception.)
"""

import datetime as dt

import pandas as pd

from vantage.index.construction import build_index

MEMBERS = [
    {"ticker": "A", "subsector": "x", "from": "2020-01-01"},
    {"ticker": "B", "subsector": "x", "from": "2020-01-01"},
]


def _prices():
    rows = [
        ("A", "2020-01-01", 10.0, 10), ("B", "2020-01-01", 20.0, 10),
        ("A", "2020-01-02", 11.0, 10), ("B", "2020-01-02", 20.0, 10),
        ("A", "2020-01-03", 11.0, 10), ("B", "2020-01-03", 22.0, 10),
    ]
    return pd.DataFrame(
        [{"ticker": t, "date": d, "close": c, "adj_close": c, "shares_out": s}
         for t, d, c, s in rows]
    )


def test_levels_match_hand_computation():
    levels, weights = build_index("VHC_TEST", MEMBERS, _prices(),
                                  base_value=100.0, base_date=dt.date(2020, 1, 1))
    pr = levels["level_pr"].tolist()
    assert abs(pr[0] - 100.0) < 1e-9
    assert abs(pr[1] - 310.0 / 3.0) < 1e-9
    assert abs(pr[2] - 110.0) < 1e-9
    # No dividends -> total return tracks price return.
    assert levels["level_tr"].tolist() == pr


def test_rebalance_weights_are_cap_weighted():
    _, weights = build_index("VHC_TEST", MEMBERS, _prices(),
                             base_value=100.0, base_date=dt.date(2020, 1, 1))
    first = weights[weights["rebalance_date"] == dt.date(2020, 1, 1)].set_index("ticker")["weight"]
    assert abs(first["A"] - 1 / 3) < 1e-9
    assert abs(first["B"] - 2 / 3) < 1e-9
