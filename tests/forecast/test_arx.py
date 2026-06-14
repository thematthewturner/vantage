"""Unit tests for the ARX forecast core (pure numpy/pandas, no DB)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from vantage.forecast import arx


def _price_path(returns: np.ndarray, start="2005-01-31") -> pd.Series:
    dates = pd.date_range(start, periods=len(returns), freq="ME")
    return pd.Series(100.0 * np.cumprod(1.0 + returns), index=dates)


def test_fit_ridge_recovers_linear_relationship():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(300, 3))
    true = np.array([1.5, -2.0, 0.5])
    y = 0.3 + X @ true + rng.normal(0, 1e-3, 300)
    mu, sd = X.mean(0), X.std(0)
    intercept, coef = arx.fit_ridge((X - mu) / sd, y, l2=1e-6)
    # Intercept is the training mean; coefficients map back to the true ones
    # through the standardisation scale.
    assert abs(intercept - y.mean()) < 1e-9
    np.testing.assert_allclose(coef, true * sd, rtol=1e-2)


def test_build_features_targets_next_month_no_lookahead():
    prices = _price_path(np.linspace(0.01, 0.02, 60), start="2010-01-31")
    X, y = arx.build_features(prices, ar_order=2)
    r = arx.monthly_returns(prices)
    t = X.index[0]
    # Target is the *next* month's return; ret_lag0 is the current known return.
    assert abs(y.loc[t] - r.shift(-1).loc[t]) < 1e-12
    assert abs(X.loc[t, "ret_lag0"] - r.loc[t]) < 1e-12
    assert {"ret_lag0", "ret_lag1"} <= set(X.columns)


def test_walk_forward_finds_autoregressive_signal():
    rng = np.random.default_rng(0)
    n, phi = 240, 0.5
    eps = rng.normal(0, 0.02, n)
    r = np.zeros(n)
    for t in range(1, n):
        r[t] = phi * r[t - 1] + eps[t]
    X, y = arx.build_features(_price_path(r), ar_order=3)
    bt = arx.walk_forward(X, y, min_train=24, l2=1.0)
    m = arx.metrics(bt)
    # A genuine AR(1) signal should beat the random-walk baseline out of sample.
    assert m["n"] > 100
    assert m["beats_baseline"] is True
    assert m["hit_rate"] > 0.5
    assert m["oos_r2"] > 0


def test_walk_forward_no_skill_on_white_noise():
    rng = np.random.default_rng(7)
    r = rng.normal(0, 0.02, 240)
    X, y = arx.build_features(_price_path(r), ar_order=3)
    m = arx.metrics(arx.walk_forward(X, y, min_train=24, l2=1.0))
    # Pure noise: no real out-of-sample explanatory power.
    assert m["n"] > 100
    assert m["oos_r2"] < 0.05


def test_metrics_empty_backtest():
    m = arx.metrics(pd.DataFrame(columns=["pred", "actual"]))
    assert m["n"] == 0 and m["beats_baseline"] is False and m["rmse"] is None
