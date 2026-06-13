"""Market-cap-weighted index construction.

Methodology (standard cap-weighted index mechanics):

* At each quarterly rebalance, target weights are set from market cap
  (close x shares outstanding) across the names that are in the universe and
  have valid data on that date.
* Between rebalances, weights are held in "buy-and-hold" form: they drift with
  relative price moves, exactly as a real cap-weighted index does. No trading
  happens between rebalances.
* The index level is a base value (100) chained forward by the daily weighted
  portfolio return. Two tracks are produced: price return (from ``close``) and
  total return (from ``adj_close``, which captures dividends).

Each day the portfolio return is computed only over names that have a valid
return that day and carried weight from the last rebalance; their weights are
renormalised so a temporarily-missing name neither adds nor subtracts return.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd


def _rebalance_dates(trading_days: pd.DatetimeIndex, rebalance: str) -> list[pd.Timestamp]:
    """First trading day in each rebalance period (plus the very first day)."""
    if len(trading_days) == 0:
        return []
    freq = {"Q": "QS", "M": "MS", "A": "AS"}.get(rebalance, "QS")
    s = pd.Series(trading_days, index=trading_days)
    # first trading day within each period bucket
    firsts = s.groupby(trading_days.to_period(freq[0])).min()
    dates = sorted({trading_days[0], *firsts.tolist()})
    return [pd.Timestamp(d) for d in dates]


def _eligible(members: list[dict], on: pd.Timestamp) -> set[str]:
    out = set()
    for m in members:
        frm = m.get("from")
        to = m.get("to")
        frm = pd.Timestamp(frm) if frm else None
        to = pd.Timestamp(to) if to else None
        if frm is not None and on < frm:
            continue
        if to is not None and on > to:
            continue
        out.add(m["ticker"])
    return out


def _chain(
    price: pd.DataFrame,
    mktcap: pd.DataFrame,
    members: list[dict],
    rebal_dates: list[pd.Timestamp],
    base_value: float,
) -> pd.Series:
    """Chain one return track to a base-value level series."""
    returns = price.pct_change()
    rebal = set(rebal_dates)
    dates = price.index
    levels = pd.Series(index=dates, dtype="float64")

    weights: pd.Series | None = None
    level = base_value
    for i, day in enumerate(dates):
        if i == 0 or day in rebal or weights is None:
            weights = _target_weights(mktcap, members, day)
            levels.iloc[i] = level
            continue

        r = returns.loc[day]
        valid = weights.index[weights.gt(0) & r.reindex(weights.index).notna()]
        if len(valid) == 0:
            levels.iloc[i] = level
            continue

        w = weights.loc[valid]
        w = w / w.sum()
        rv = r.reindex(valid).astype("float64")
        port_ret = float((w * rv).sum())
        level *= 1.0 + port_ret
        levels.iloc[i] = level

        # drift weights for next day
        grown = w * (1.0 + rv)
        weights = grown / grown.sum()
    return levels


def _target_weights(mktcap: pd.DataFrame, members: list[dict], day: pd.Timestamp) -> pd.Series:
    elig = _eligible(members, day)
    caps = mktcap.loc[day].reindex(sorted(elig)).dropna()
    caps = caps[caps > 0]
    if caps.empty:
        return pd.Series(dtype="float64")
    return caps / caps.sum()


def build_index(
    index_id: str,
    members: list[dict],
    prices: pd.DataFrame,
    *,
    base_value: float = 100.0,
    base_date: dt.date | None = None,
    rebalance: str = "Q",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build one index. Returns (levels, weights).

    levels columns: date, level_pr, level_tr
    weights columns: rebalance_date, ticker, weight (price-return market caps)
    """
    tickers = {m["ticker"] for m in members}
    prices = prices[prices["ticker"].isin(tickers)].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    if base_date is not None:
        prices = prices[prices["date"] >= pd.Timestamp(base_date)]

    if prices.empty:
        empty_lv = pd.DataFrame(columns=["date", "level_pr", "level_tr"])
        empty_wt = pd.DataFrame(columns=["rebalance_date", "ticker", "weight"])
        return empty_lv, empty_wt

    close = prices.pivot(index="date", columns="ticker", values="close").sort_index()
    adj = prices.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    shares = prices.pivot(index="date", columns="ticker", values="shares_out").sort_index()
    mktcap = close * shares

    rebal_dates = _rebalance_dates(close.index, rebalance)

    level_pr = _chain(close, mktcap, members, rebal_dates, base_value)
    level_tr = _chain(adj, mktcap, members, rebal_dates, base_value)

    levels = pd.DataFrame(
        {
            "date": level_pr.index.date,
            "level_pr": level_pr.to_numpy(),
            "level_tr": level_tr.to_numpy(),
        }
    )

    wt_rows = []
    for day in rebal_dates:
        w = _target_weights(mktcap, members, day)
        for ticker, weight in w.items():
            wt_rows.append(
                {"rebalance_date": day.date(), "ticker": ticker, "weight": float(weight)}
            )
    weights = pd.DataFrame(wt_rows, columns=["rebalance_date", "ticker", "weight"])
    return levels, weights
