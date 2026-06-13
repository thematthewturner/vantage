"""The vantage terminal -- a dark, multi-chart healthcare research dashboard.

Run locally with ``make dash`` (``streamlit run src/vantage/app/dashboard.py``)
or in production behind Docker (see ``deploy/``). It is read-only: the nightly
``vantage.pipeline.refresh`` writes the store, this only draws it.
"""

from __future__ import annotations

import hmac
import os

import pandas as pd
import streamlit as st

from vantage.app import charts, data
from vantage.transforms.correlation import honesty_report, lead_lag
from vantage.transforms.signals import yoy

st.set_page_config(page_title="vantage terminal", page_icon="\U0001fa7a", layout="wide")

_NO_MODEBAR = {"displayModeBar": False}
_SUBSECTOR_ORDER = ["prices", "labor", "spending", "macro"]


# --- access gate -----------------------------------------------------------


def _check_password() -> bool:
    """Optional single-password gate, on only if VANTAGE_DASHBOARD_PASSWORD is set."""
    secret = os.environ.get("VANTAGE_DASHBOARD_PASSWORD")
    if not secret:
        return True
    if st.session_state.get("_auth_ok"):
        return True

    with st.form("login"):
        st.text_input("Password", type="password", key="_pw")
        if st.form_submit_button("Enter") and hmac.compare_digest(
            st.session_state.get("_pw", ""), secret
        ):
            st.session_state["_auth_ok"] = True
            st.rerun()
    if "_pw" in st.session_state and not st.session_state.get("_auth_ok"):
        st.error("Incorrect password.")
    return False


# --- helpers ---------------------------------------------------------------


def _index_label(index_id: str) -> str:
    return "VHC (whole universe)" if index_id == "VHC" else index_id.replace("VHC_", "").title()


def _fmt_pct(x: float | None) -> str:
    return "--" if x is None or pd.isna(x) else f"{x:+.1f}%"


def _fmt_dt(ts) -> str:
    return "never" if ts is None or pd.isna(ts) else pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M")


def _pct_color(v) -> str:
    """Red/green text for a percentage cell (no matplotlib needed)."""
    if v is None or pd.isna(v):
        return "color: #6b7280"
    return f"color: {charts.GREEN if v >= 0 else charts.RED}"


# --- status bar ------------------------------------------------------------


def render_status_bar() -> None:
    h = data.health()
    vhc = data.index_track("VHC")
    perf = data.performance_summary(vhc["level_tr"]) if not vhc.empty else {}
    last_level = float(vhc["level_tr"].dropna().iloc[-1]) if not vhc.empty else None

    cols = st.columns([1.4, 1, 1, 1, 1.3, 1.3])
    cols[0].metric(
        "VHC (TR)", f"{last_level:,.1f}" if last_level else "--", _fmt_pct(perf.get("1D"))
    )
    cols[1].metric("MTD", _fmt_pct(perf.get("1M")))
    cols[2].metric("YTD", _fmt_pct(perf.get("YTD")))
    cols[3].metric("1Y", _fmt_pct(perf.get("1Y")))
    cols[4].metric("Indicators / names", f"{h['n_indicators']} / {h['n_securities']}")
    cols[5].metric("Last refresh (UTC)", _fmt_dt(h["last_fetched"]))


# --- tabs ------------------------------------------------------------------


def tab_index() -> None:
    indices = data.available_indices()
    if not indices:
        st.info("No index built yet. Run the refresh to ingest prices and build VHC.")
        return

    track = st.radio("Track", ["Total return", "Price return"], horizontal=True, index=0)
    track_col = "level_tr" if track == "Total return" else "level_pr"

    left, right = st.columns([2, 1])
    with left:
        vhc = data.index_track("VHC")
        if not vhc.empty:
            st.plotly_chart(charts.index_chart(vhc, "VHC — healthcare composite"), width="stretch")
    with right:
        st.markdown("**Performance (total return)**")
        rows = []
        for idx in indices:
            t = data.index_track(idx)
            if t.empty:
                continue
            p = data.performance_summary(t["level_tr"])
            rows.append({"Index": _index_label(idx), **p})
        if rows:
            perf_df = pd.DataFrame(rows).set_index("Index")
            st.dataframe(
                perf_df.style.format("{:+.1f}%", na_rep="--").map(_pct_color),
                width="stretch",
            )

    st.markdown("#### Sub-sector indices (rebased to 100)")
    subs = data.subsector_tracks(track_col)
    if not subs.empty:
        st.plotly_chart(charts.overlay_chart(subs, ""), width="stretch", config=_NO_MODEBAR)
        # Small multiples: one mini panel per sub-sector.
        grid = st.columns(4)
        for i, col in enumerate(subs.columns):
            with grid[i % 4]:
                st.caption(col.title())
                st.plotly_chart(
                    charts.sparkline(subs[col]),
                    width="stretch",
                    config=_NO_MODEBAR,
                    key=f"sm_{col}",
                )

    st.markdown("#### Latest constituent weights")
    pick = st.selectbox("Index", indices, format_func=_index_label, key="weights_index")
    w = data.latest_weights(pick)
    if not w.empty:
        c1, c2 = st.columns([1, 1])
        c1.plotly_chart(
            charts.weights_bar(w, _index_label(pick)), width="stretch", config=_NO_MODEBAR
        )
        c2.dataframe(
            w.assign(weight=(w["weight"] * 100).round(2))[
                ["ticker", "name", "subsector", "weight"]
            ],
            width="stretch",
            hide_index=True,
        )


def tab_indicators() -> None:
    cat = data.series_catalog()
    if cat.empty:
        st.info("No indicators ingested yet. Set FRED_API_KEY and run the refresh.")
        return

    groups = list(cat["subsector"].dropna().unique())
    ordered = [g for g in _SUBSECTOR_ORDER if g in groups] + [
        g for g in groups if g not in _SUBSECTOR_ORDER
    ]

    for group in ordered:
        st.markdown(f"#### {group.title()}")
        members = cat[cat["subsector"] == group]
        grid = st.columns(3)
        for i, (_, row) in enumerate(members.iterrows()):
            series = data.indicator_series(row["source"], row["series_id"])
            snap = data.indicator_snapshot(
                series["value"] if not series.empty else pd.Series(dtype=float), row["frequency"]
            )
            with grid[i % 3].container(border=True):
                st.caption(row["metric_name"])
                st.metric(
                    label=row["unit"] or row["series_id"],
                    value=f"{snap['latest']:,.1f}" if snap["latest"] is not None else "--",
                    delta=_fmt_pct(None if snap["yoy"] is None else snap["yoy"] * 100) + " YoY",
                )
                z = snap["zscore"]
                st.caption(f"z-score: {z:+.2f}" if z is not None else "z-score: --")
                if not snap["spark"].empty:
                    st.plotly_chart(
                        charts.sparkline(snap["spark"]),
                        width="stretch",
                        config=_NO_MODEBAR,
                        key=f"sp_{row['series_id']}",
                    )

    st.divider()
    st.markdown("#### Indicator detail")
    label_map = {f"{r['metric_name']} ({r['series_id']})": r for _, r in cat.iterrows()}
    choice = st.selectbox("Series", list(label_map), key="ind_detail")
    row = label_map[choice]
    series = data.indicator_series(row["source"], row["series_id"])
    if not series.empty:
        level = series["value"]
        yoy_s = yoy(level) * 100
        st.plotly_chart(
            charts.dual_axis_chart(level, yoy_s, row["metric_name"], "YoY %"),
            width="stretch",
        )


def _monthly_yoy(series: pd.Series) -> pd.Series:
    return yoy(series.resample("MS").last())


def tab_leadlag() -> None:
    cat = data.series_catalog()
    vhc = data.index_track("VHC")
    if cat.empty or vhc.empty:
        st.info("Need both an index and indicators. Run the refresh first.")
        return

    st.caption(
        "Cross-correlation on **stationary** (monthly YoY) transforms. Positive lag = "
        "indicator leads the index. These are hypotheses, not signals — read the honesty "
        "report below."
    )
    vhc_yoy = _monthly_yoy(vhc["level_tr"])
    max_lag = st.slider("Max lag (months)", 3, 24, 12)

    c1, c2 = st.columns(2)
    label_map = {f"{r['metric_name']} ({r['series_id']})": r for _, r in cat.iterrows()}
    choice = c1.selectbox("Indicator", list(label_map), key="ll_indicator")
    row = label_map[choice]
    ind = data.indicator_series(row["source"], row["series_id"])

    if not ind.empty:
        ind_yoy = _monthly_yoy(ind["value"])
        res = lead_lag(ind_yoy, vhc_yoy, max_lag=max_lag)
        c1.plotly_chart(
            charts.dual_axis_chart(vhc["level_tr"], ind["value"], "VHC (TR)", row["metric_name"]),
            width="stretch",
        )
        c2.plotly_chart(charts.leadlag_bars(res, f"{row['metric_name']} vs VHC"), width="stretch")

        rep = honesty_report(res, n_indicators_tested=len(cat))
        st.markdown("##### Honesty report")
        for w in rep["warnings"]:
            st.warning(w, icon="⚠️")
        m = st.columns(3)
        m[0].metric("Best lag (months)", rep["best_lag"] if rep["best_lag"] is not None else "--")
        m[1].metric(
            "Correlation", f"{rep['best_corr']:+.2f}" if rep["best_corr"] is not None else "--"
        )
        m[2].metric("Combinations tested", rep["combinations_tested"])

    st.divider()
    st.markdown("#### Lead-lag heatmap (all indicators)")
    st.caption(
        "Every indicator x lag in one view. Bright cells across many indicators are mostly noise."
    )
    matrix = {}
    lags = list(range(-max_lag, max_lag + 1))
    for _, r in cat.iterrows():
        s = data.indicator_series(r["source"], r["series_id"])
        if s.empty:
            continue
        res = lead_lag(_monthly_yoy(s["value"]), vhc_yoy, max_lag=max_lag)
        matrix[r["metric_name"]] = res.set_index("lag")["corr"].reindex(lags)
    if matrix:
        mat = pd.DataFrame(matrix).T
        st.plotly_chart(charts.correlation_heatmap(mat, ""), width="stretch", config=_NO_MODEBAR)


def tab_health() -> None:
    h = data.health()
    cols = st.columns(4)
    cols[0].metric("Indicators", h["n_indicators"])
    cols[1].metric("Constituents", h["n_securities"])
    cols[2].metric("Indices built", h["n_indices"])
    cols[3].metric("Latest price", _fmt_dt(h["last_price"]))

    st.markdown("#### Series freshness")
    cat = data.series_catalog()
    if not cat.empty:
        view = cat.copy()
        view["stale"] = [
            data.staleness(lo, fr)
            for lo, fr in zip(view["last_obs"], view["frequency"], strict=False)
        ]
        st.dataframe(
            view[
                [
                    "metric_name",
                    "frequency",
                    "unit",
                    "subsector",
                    "last_obs",
                    "last_fetched",
                    "stale",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    st.markdown("#### Price coverage")
    cov = data.price_coverage()
    if not cov.empty:
        st.dataframe(cov, width="stretch", hide_index=True)
    st.caption(f"Store: `{data.db_path()}`")


# --- main ------------------------------------------------------------------


def main() -> None:
    if not _check_password():
        return

    st.title("\U0001fa7a vantage terminal")
    st.caption("Healthcare industry trackers + a custom health-stock index. Not investment advice.")

    if not data.db_exists():
        st.warning(
            "No data store yet. Set `FRED_API_KEY`, then run `make refresh` "
            "(or wait for the nightly scheduler) to ingest data and build the index."
        )
        return

    render_status_bar()
    st.divider()

    index_t, indicators_t, leadlag_t, health_t = st.tabs(
        [
            "\U0001f4c8 Index",
            "\U0001f4ca Indicators",
            "\U0001f517 Lead-Lag",
            "\U0001fa7a Data health",
        ]
    )
    with index_t:
        tab_index()
    with indicators_t:
        tab_indicators()
    with leadlag_t:
        tab_leadlag()
    with health_t:
        tab_health()


main()
