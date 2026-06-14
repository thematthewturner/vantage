"""Per-stock next-month return forecasting: an autoregressive model with
exogenous inputs (ARX), evaluated by leakage-free walk-forward backtest.

Design choices, all in the service of *not fooling ourselves* (the same spirit
as the lead-lag honesty report):

* **Monthly horizon.** We predict the next calendar month's simple return from
  information knowable at month end. Daily/weekly returns are essentially noise;
  monthly gives the macro indicators a chance to matter.
* **ARX features.** Autoregressive lags of the stock's own monthly returns, plus
  exogenous features: each indicator's YoY change (made stationary and lagged a
  month for publication delay), and trailing sector- and market-index momentum.
* **No look-ahead.** Every feature at month ``t`` uses only data through ``t``;
  the target is the return from ``t`` to ``t+1``. The backtest is walk-forward:
  at each step we fit only on months whose target had already been realised, and
  standardise features with training-window statistics only.
* **Honest scoring.** Predictions are compared against the random-walk baseline
  (predict zero). The headline is whether the model beats that baseline out of
  sample at all -- across 28 stocks, some will look good by chance, so we report
  RMSE-vs-baseline, out-of-sample R², and directional hit rate together.

Everything here is pure (numpy/pandas only) and unit-tested; the dashboard and
pipeline are thin callers.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from vantage.transforms.signals import yoy

DEFAULT_AR_ORDER = 3
DEFAULT_L2 = 10.0
DEFAULT_MIN_TRAIN = 36  # months of realised targets before the first prediction
DEFAULT_MOMENTUM = 3  # trailing months for index momentum features


# --- feature construction --------------------------------------------------


def monthly_returns(prices: pd.Series) -> pd.Series:
    """Month-end simple returns from a (daily) price series."""
    s = prices.dropna()
    if s.empty:
        return pd.Series(dtype=float)
    monthly = s.resample("ME").last()
    return monthly.pct_change().dropna()


def _momentum(index_level: pd.Series, window: int) -> pd.Series:
    """Trailing `window`-month return of an index level, at month end."""
    monthly = index_level.dropna().resample("ME").last()
    return monthly.pct_change(window)


def build_features(
    stock_prices: pd.Series,
    *,
    exog: pd.DataFrame | None = None,
    sector_index: pd.Series | None = None,
    market_index: pd.Series | None = None,
    ar_order: int = DEFAULT_AR_ORDER,
    exog_lag: int = 1,
    momentum_window: int = DEFAULT_MOMENTUM,
) -> tuple[pd.DataFrame, pd.Series]:
    """Assemble the monthly ARX design matrix `X` and next-month target `y`.

    `X` rows are indexed by month end `t` and use only information knowable at
    `t`; `y[t]` is the return from `t` to `t+1`. Returns complete cases only
    (rows with any missing feature or target are dropped), so the backtest never
    has to reason about gaps.
    """
    r = monthly_returns(stock_prices)
    if r.empty:
        return pd.DataFrame(), pd.Series(dtype=float)

    feats: dict[str, pd.Series] = {}
    # Autoregressive terms: the most recent known monthly returns r_t, r_{t-1}, ...
    for lag in range(ar_order):
        feats[f"ret_lag{lag}"] = r.shift(lag)

    monthly_index = r.index
    if exog is not None and not exog.empty:
        ex = exog.copy()
        ex.index = pd.to_datetime(ex.index)
        ex_m = ex.resample("ME").last()
        for col in ex_m.columns:
            # Stationary transform + publication-lag shift, then align to r's months.
            transformed = yoy(ex_m[col]).shift(exog_lag)
            feats[f"exog_{col}"] = transformed.reindex(monthly_index, method="ffill")

    if sector_index is not None and not sector_index.empty:
        feats["sector_mom"] = _momentum(sector_index, momentum_window).reindex(
            monthly_index, method="ffill"
        )
    if market_index is not None and not market_index.empty:
        feats["market_mom"] = _momentum(market_index, momentum_window).reindex(
            monthly_index, method="ffill"
        )

    X = pd.DataFrame(feats, index=monthly_index)
    y = r.shift(-1).rename("target")  # next-month return
    data = X.join(y).dropna()
    if data.empty:
        return pd.DataFrame(), pd.Series(dtype=float)
    return data[list(X.columns)], data["target"]


# --- ridge regression (closed form) ----------------------------------------


def fit_ridge(X: np.ndarray, y: np.ndarray, l2: float) -> tuple[float, np.ndarray]:
    """L2-regularised least squares on standardised `X`. Returns (intercept, coef).

    `X` is assumed already standardised (zero mean, unit std per column); the
    intercept is the training mean of `y`, so the penalty never shrinks it.
    """
    n, k = X.shape
    intercept = float(y.mean())
    gram = X.T @ X + l2 * np.eye(k)
    coef = np.linalg.solve(gram, X.T @ (y - intercept))
    return intercept, coef


def predict_ridge(X: np.ndarray, intercept: float, coef: np.ndarray) -> np.ndarray:
    return intercept + X @ coef


# --- walk-forward backtest --------------------------------------------------


def walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    *,
    min_train: int = DEFAULT_MIN_TRAIN,
    l2: float = DEFAULT_L2,
) -> pd.DataFrame:
    """One-step-ahead expanding-window backtest.

    For each month from `min_train` onward, fit on all earlier complete months
    and predict that month's target. Features are standardised with training
    statistics only (no peeking at the test row). Returns a date-indexed frame
    with `pred` and `actual` columns.
    """
    if len(X) <= min_train:
        return pd.DataFrame(columns=["pred", "actual"])
    Xv = X.to_numpy(dtype=float)
    yv = y.to_numpy(dtype=float)
    rows: list[tuple[pd.Timestamp, float, float]] = []
    for i in range(min_train, len(X)):
        Xtr, ytr = Xv[:i], yv[:i]
        mu = Xtr.mean(axis=0)
        sd = Xtr.std(axis=0)
        sd[sd == 0] = 1.0
        intercept, coef = fit_ridge((Xtr - mu) / sd, ytr, l2)
        x_test = (Xv[i] - mu) / sd
        rows.append((X.index[i], float(predict_ridge(x_test, intercept, coef)), float(yv[i])))
    return pd.DataFrame(rows, columns=["date", "pred", "actual"]).set_index("date")


def metrics(backtest: pd.DataFrame) -> dict:
    """Honest out-of-sample scorecard for a walk-forward `backtest`.

    `rmse` vs `rmse_baseline` (predict zero = random walk) is the headline:
    `beats_baseline` is True only when the model's error is actually smaller.
    `oos_r2` is relative to predicting zero, so a negative value (common!) means
    worse than doing nothing. `hit_rate` is directional accuracy (~0.5 = none).
    """
    empty = {
        "n": 0,
        "rmse": None,
        "rmse_baseline": None,
        "oos_r2": None,
        "hit_rate": None,
        "beats_baseline": False,
    }
    if backtest is None or backtest.empty:
        return empty
    pred = backtest["pred"].to_numpy(dtype=float)
    actual = backtest["actual"].to_numpy(dtype=float)
    n = len(actual)
    ss_res = float(np.sum((actual - pred) ** 2))
    ss_base = float(np.sum(actual**2))  # baseline predicts zero
    rmse = math.sqrt(ss_res / n)
    rmse_base = math.sqrt(ss_base / n)
    oos_r2 = 1.0 - ss_res / ss_base if ss_base > 0 else None
    nonzero = actual != 0
    hit_rate = (
        float(np.mean(np.sign(pred[nonzero]) == np.sign(actual[nonzero])))
        if nonzero.any()
        else None
    )
    return {
        "n": n,
        "rmse": rmse,
        "rmse_baseline": rmse_base,
        "oos_r2": oos_r2,
        "hit_rate": hit_rate,
        "beats_baseline": rmse < rmse_base,
    }


def backtest_stock(
    stock_prices: pd.Series,
    *,
    exog: pd.DataFrame | None = None,
    sector_index: pd.Series | None = None,
    market_index: pd.Series | None = None,
    ar_order: int = DEFAULT_AR_ORDER,
    l2: float = DEFAULT_L2,
    min_train: int = DEFAULT_MIN_TRAIN,
) -> tuple[pd.DataFrame, dict]:
    """Build features, run the walk-forward backtest, and score it for one stock."""
    X, y = build_features(
        stock_prices,
        exog=exog,
        sector_index=sector_index,
        market_index=market_index,
        ar_order=ar_order,
    )
    if X.empty:
        return pd.DataFrame(columns=["pred", "actual"]), metrics(pd.DataFrame())
    bt = walk_forward(X, y, min_train=min_train, l2=l2)
    return bt, metrics(bt)
