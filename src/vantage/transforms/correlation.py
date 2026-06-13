"""Lead-lag correlation analysis -- built to stay honest.

The point of this module is to *explore* whether an industry indicator leads or
lags the health-stock index, while making the statistical traps impossible to
ignore:

* Correlations are computed on **stationary** transforms (the caller passes
  YoY/diff series, not raw trending levels) -- two trending series correlate
  spuriously.
* The result reports **effective sample size** per lag, not just a coefficient.
* ``honesty_report`` surfaces the multiple-comparisons exposure (indicators x
  lags tested) so a cherry-picked headline correlation can't hide.

Nothing here is a trading signal. Treat findings as hypotheses.
"""

from __future__ import annotations

import pandas as pd


def lead_lag(indicator: pd.Series, target: pd.Series, *, max_lag: int = 12) -> pd.DataFrame:
    """Cross-correlation of indicator(t - lag) vs target(t) for lag in -max..+max.

    Positive lag = indicator leads the target. Both series should already be
    stationary (e.g. YoY changes) and on the same frequency/index.

    Returns columns: lag, corr, n (effective non-null pairs).
    """
    df = pd.DataFrame({"ind": indicator, "tgt": target}).dropna(how="all")
    rows = []
    for lag in range(-max_lag, max_lag + 1):
        shifted = df["ind"].shift(lag)
        pair = pd.DataFrame({"ind": shifted, "tgt": df["tgt"]}).dropna()
        n = len(pair)
        corr = pair["ind"].corr(pair["tgt"]) if n >= 3 else float("nan")
        rows.append({"lag": lag, "corr": corr, "n": n})
    return pd.DataFrame(rows)


def honesty_report(result: pd.DataFrame, *, n_indicators_tested: int = 1) -> dict:
    """Flag the ways a lead-lag result could be misleading.

    `result` is the output of `lead_lag`. `n_indicators_tested` is how many
    indicators you scanned in total (for the multiple-comparisons count).
    """
    valid = result.dropna(subset=["corr"])
    best = valid.loc[valid["corr"].abs().idxmax()] if not valid.empty else None
    n_lags = len(result)
    combinations = n_lags * max(1, n_indicators_tested)
    min_n = int(result["n"].min()) if not result.empty else 0

    return {
        "best_lag": None if best is None else int(best["lag"]),
        "best_corr": None if best is None else float(best["corr"]),
        "best_n": None if best is None else int(best["n"]),
        "combinations_tested": combinations,
        "small_sample": min_n < 30,
        "warnings": [
            w for w in [
                "Small effective sample (<30) at one or more lags; correlations unstable."
                if min_n < 30 else None,
                f"{combinations} indicator x lag combinations tested; expect spurious "
                "'significant' hits by chance. Prefer a pre-registered hypothesis."
                if combinations > 20 else None,
                "Exploratory only -- not a predictive or trading signal.",
            ] if w
        ],
    }
