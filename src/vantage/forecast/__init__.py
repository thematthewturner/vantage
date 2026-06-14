"""Per-stock next-month ARX return forecasting and leakage-free backtesting."""

from vantage.forecast.arx import (
    backtest_stock,
    build_features,
    fit_ridge,
    metrics,
    monthly_returns,
    predict_ridge,
    walk_forward,
)

__all__ = [
    "backtest_stock",
    "build_features",
    "fit_ridge",
    "metrics",
    "monthly_returns",
    "predict_ridge",
    "walk_forward",
]
