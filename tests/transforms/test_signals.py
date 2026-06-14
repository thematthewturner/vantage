import numpy as np
import pandas as pd

from vantage.transforms.align import asof_align
from vantage.transforms.correlation import honesty_report, lead_lag
from vantage.transforms.signals import relative_strength, yoy, zscore


def test_yoy_explicit_periods():
    idx = pd.date_range("2020-01-01", periods=13, freq="MS")
    s = pd.Series(range(100, 113), index=idx, dtype="float64")
    out = yoy(s, periods=12)
    assert np.isnan(out.iloc[0])
    # value 12 months later: (112-100)/100
    assert abs(out.iloc[12] - 0.12) < 1e-12


def test_zscore_is_trailing():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    z = zscore(s, window=3)
    # First two are NaN (window not full); third uses [1,2,3]: mean 2, std 1 -> z=1
    assert np.isnan(z.iloc[1])
    assert abs(z.iloc[2] - 1.0) < 1e-12


def test_asof_align_never_looks_ahead():
    index = pd.Series(
        [1.0, 1.0, 1.0], index=pd.to_datetime(["2020-01-10", "2020-01-20", "2020-02-10"])
    )
    indicator = pd.Series([10.0, 20.0], index=pd.to_datetime(["2020-01-01", "2020-02-01"]))
    out = asof_align(index, indicator)
    # Jan dates only see the Jan-01 print; Feb-10 sees the Feb-01 print.
    assert out["indicator"].tolist() == [10.0, 10.0, 20.0]


def test_lead_lag_recovers_known_lead():
    idx = pd.date_range("2020-01-01", periods=60, freq="MS")
    rng = np.random.default_rng(0)
    ind = pd.Series(rng.normal(size=60), index=idx)
    tgt = ind.shift(2)  # target lags indicator by 2 -> indicator leads by 2
    res = lead_lag(ind, tgt, max_lag=6)
    best = res.loc[res["corr"].abs().idxmax()]
    assert int(best["lag"]) == 2
    assert best["corr"] > 0.99


def test_honesty_report_flags_multiple_comparisons():
    idx = pd.date_range("2020-01-01", periods=40, freq="MS")
    ind = pd.Series(range(40), index=idx, dtype="float64")
    res = lead_lag(ind, ind, max_lag=12)
    rep = honesty_report(res, n_indicators_tested=10)
    assert rep["combinations_tested"] == 25 * 10
    assert any("combinations tested" in w for w in rep["warnings"])


def test_relative_strength_rebases_and_tracks_outperformance():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    series = pd.Series([100.0, 110.0, 121.0], index=idx)  # +10%, +10%
    bench = pd.Series([100.0, 100.0, 100.0], index=idx)  # flat
    rs = relative_strength(series, bench)
    assert rs.iloc[0] == 100.0  # always rebased to base at the common start
    assert abs(rs.iloc[-1] - 121.0) < 1e-9  # outperformance compounds above 100

    # A benchmark that beats the series drives the line below 100.
    rs_lag = relative_strength(bench, series)
    assert rs_lag.iloc[-1] < 100.0


def test_relative_strength_aligns_on_common_dates_only():
    a = pd.Series([100.0, 110.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
    b = pd.Series([100.0, 200.0], index=pd.to_datetime(["2020-01-02", "2020-01-03"]))
    rs = relative_strength(a, b)  # only 2020-01-02 overlaps
    assert rs.index.tolist() == [pd.Timestamp("2020-01-02")]
    assert rs.iloc[0] == 100.0


def test_relative_strength_empty_when_no_overlap():
    a = pd.Series([100.0], index=pd.to_datetime(["2020-01-01"]))
    b = pd.Series([100.0], index=pd.to_datetime(["2021-01-01"]))
    assert relative_strength(a, b).empty
